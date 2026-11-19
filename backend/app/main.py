from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import json
import zlib
from .routing import draft_route, network, nearby_connections, edge_key, connection_label, STEP_FREE_STATES
from . import ai_assistant, assistant_scope, assistant_answers
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from difflib import SequenceMatcher
from typing import Annotated
from urllib.parse import urlsplit
from uuid import uuid4

import jwt
from fastapi import Depends, FastAPI, HTTPException, Query, status, Request, Response, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import or_, func, Column, DateTime, inspect, text
from sqlalchemy.types import TypeDecorator
from sqlmodel import Field, Session, SQLModel, create_engine, select

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sdu_campus.db")
# Hosts such as Neon hand out postgres:// or postgresql:// addresses; use the installed psycopg 3 driver.
DATABASE_URL = re.sub(r"^postgres(ql)?://", "postgresql+psycopg://", DATABASE_URL)
JWT_SECRET = os.getenv("JWT_SECRET", "sdu-campus-course-demo-secret")
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
security = HTTPBearer(auto_error=False)
ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
if COOKIE_SECURE and JWT_SECRET == "sdu-campus-course-demo-secret":
    # The demo secret is public in this repository; never sign real sessions with it.
    # A random secret is safe, but everyone is signed out whenever the server restarts.
    print("JWT_SECRET is not set; using a random secret for this run.")
    JWT_SECRET = secrets.token_urlsafe(48)
COOKIE_NAME = "sdu_session"
TZ = ZoneInfo("Asia/Almaty")
CAMPUS_MAP = json.loads((Path(__file__).parent / 'data/campus.json').read_text())
MAP_LOCATIONS = {p['id']: p for p in CAMPUS_MAP['places']}
MAP_IMPORT_MARKER = "[campus-map-v1]"
RETIRED_LOCATION_IDS = [4, 5, 8, 9, 10, 11, 12, 1000 + zlib.crc32(b'stair_main_01') % 100000000]


class BrowserSession(SQLModel, table=True):
    id: str = Field(primary_key=True)
    subject: str = Field(index=True)
    csrf: str
    expires_at: datetime
    revoked: bool = False


class AssistantContext(SQLModel, table=True):
    id: str = Field(primary_key=True)
    actor: str
    choices_json: str
    route_intent: bool = False
    expires_at: datetime


class AssistantConversation(SQLModel, table=True):
    id: str = Field(primary_key=True)
    actor: str = Field(index=True)
    messages_json: str = "[]"
    expires_at: datetime


class UTCDateTime(TypeDecorator):
    """Persist UTC even on SQLite, which drops the timezone from DateTime values."""
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=timezone.utc) if value is not None else None


class SampleLesson(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    course: str
    starts_at: datetime = Field(sa_column=Column(UTCDateTime(), nullable=False))
    location_id: int | None = None
    room: str
    kind: str = "student"
    sample: bool = True


class DataMigration(SQLModel, table=True):
    key: str = Field(primary_key=True)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    full_name: str
    email: str = Field(index=True, unique=True)
    role: str = Field(default="student", index=True)
    faculty: str = "SDU"
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuthAccount(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    sdu_id: str = Field(index=True, unique=True)
    password_hash: str
    user_id: int = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GuestSession(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    session_key: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RoleOverride(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    role: str
    reason: str = "Seeded course demonstration role"


class Preference(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    accessible_routes: bool = False


class GuestPreference(SQLModel, table=True):
    session_key: str = Field(primary_key=True)
    accessible_routes: bool = False


class Location(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    category: str = Field(index=True)
    block: str = Field(index=True)
    floor: str
    x: float
    y: float
    opening_hours: str = "Not confirmed"
    contact: str = "Not confirmed"
    accessible: bool = True
    aliases: str = ""
    step_free_access: str = "Not verified"


class Route(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    start_location_id: int
    destination_location_id: int
    distance_m: int
    duration_min: int
    accessible: bool = False


class RouteStep(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    route_id: int = Field(index=True)
    step_order: int
    instruction: str


class Favorite(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    location_id: int = Field(index=True)


class CampusClass(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    owner_email: str = Field(index=True)
    course: str
    room: str
    starts_at: str
    location_id: int
    kind: str = "student"


class Announcement(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    body: str
    published_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    location_id: int | None = None
    starts_at: datetime | None = Field(default=None, sa_column=Column(UTCDateTime(), nullable=True))
    ends_at: datetime | None = Field(default=None, sa_column=Column(UTCDateTime(), nullable=True))


class InaccuracyReport(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    author: str
    location_id: int | None = None
    message: str
    status: str = Field(default="new", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    kind: str = "location"
    edge_a: str | None = None
    edge_b: str | None = None
    route_start_id: int | None = None
    route_destination_id: int | None = None
    resolution_note: str = ""
    updated_at: datetime | None = None
    reporter_unread: bool = False


class PathStatus(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    edge_a: str = Field(index=True)
    edge_b: str = Field(index=True)
    state: str
    note: str = ""
    report_id: int | None = None
    active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reopens_at: datetime | None = Field(default=None, sa_column=Column(UTCDateTime(), nullable=True))


class SearchLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    actor: str
    query: str = Field(index=True)
    selected_location_id: int | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LoginRequest(BaseModel):
    sdu_id: str
    password: str


class RegisterRequest(BaseModel):
    sdu_id: str
    full_name: str
    password: str


class ReportRequest(BaseModel):
    message: str
    location_id: int | None = None
    kind: str = "location"
    edge_a: str | None = None
    edge_b: str | None = None
    route_start_id: int | None = None
    route_destination_id: int | None = None


class ReportUpdateRequest(BaseModel):
    status: str
    resolution_note: str | None = None


class PathStatusRequest(BaseModel):
    edge_a: str
    edge_b: str
    state: str
    note: str = ""
    report_id: int | None = None
    reopens_at: datetime | None = None


class AssistantRequest(BaseModel):
    question: str = ""
    conversation_id: str | None = None
    context_id: str | None = None
    selection_id: int | None = None


class RoleRequest(BaseModel):
    role: str


class PreferenceRequest(BaseModel):
    accessible_routes: bool


class LocationDetailsRequest(BaseModel):
    """Editable details only. Category, position and route connections come from the campus map file."""
    name: str
    block: str
    floor: str
    opening_hours: str = "Not confirmed"
    contact: str = "Not confirmed"
    aliases: str = ""
    step_free_access: str = "Not verified"
    report_id: int | None = None
    resolution_note: str | None = None


def get_session():
    with Session(engine) as session:
        yield session


DbSession = Annotated[Session, Depends(get_session)]


def make_token(subject: str, role: str) -> str:
    payload = {"sub": subject, "role": role, "exp": datetime.now(timezone.utc) + timedelta(hours=12)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def normalize_sdu_id(value: str) -> str:
    sdu_id = value.strip()
    if not re.fullmatch(r"[0-9]{9}", sdu_id):
        raise HTTPException(status_code=422, detail="Enter your 9-digit SDU ID")
    return sdu_id


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
    iterations = 600_000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return "$".join([
        "pbkdf2-sha256",
        str(iterations),
        base64.urlsafe_b64encode(salt).decode(),
        base64.urlsafe_b64encode(digest).decode(),
    ])


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, raw_iterations, raw_salt, raw_digest = encoded.split("$", 3)
        if algorithm != "pbkdf2-sha256":
            return False
        salt = base64.urlsafe_b64decode(raw_salt.encode())
        expected = base64.urlsafe_b64decode(raw_digest.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(raw_iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def user_for_identity(identity: dict, session: Session) -> User | None:
    subject = identity["sub"]
    if re.fullmatch(r"[0-9]{9}", subject):
        account = session.exec(select(AuthAccount).where(AuthAccount.sdu_id == subject)).first()
        return session.get(User, account.user_id) if account else None
    if "@" in subject:
        return session.exec(select(User).where(User.email == subject)).first()
    return None


def resolve_identity(request: Request, session: Session, required: bool = True) -> dict | None:
    authorization = request.headers.get("authorization", "")
    token = authorization[7:] if authorization.lower().startswith("bearer ") else request.cookies.get(COOKIE_NAME)
    if not token:
        if required:
            raise HTTPException(401, "Authentication required")
        return None
    try:
        identity = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "Invalid or expired session") from exc
    if identity.get("jti"):
        record = session.get(BrowserSession, identity["jti"])
        if not record or record.revoked or as_utc(record.expires_at) <= datetime.now(timezone.utc):
            raise HTTPException(401, "Session has ended. Please log in again.")
        if not authorization and request.method not in {"GET", "HEAD", "OPTIONS"}:
            if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), record.csrf):
                raise HTTPException(403, "Session security check failed. Refresh and try again.")
    elif not authorization:
        raise HTTPException(401, "Please sign in to create a browser session")
    user = user_for_identity(identity, session)
    if user:
        if not user.active:
            raise HTTPException(403, "This account is unavailable")
        identity["role"] = user.role
    elif identity.get("role") != "guest" or not session.exec(select(GuestSession).where(GuestSession.session_key == identity["sub"])).first():
        raise HTTPException(401, "Account not found")
    return identity


def current_identity(request: Request, session: DbSession,
                     credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
                     x_csrf_token: Annotated[str | None, Header()] = None) -> dict:
    return resolve_identity(request, session)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def issue_session(subject: str, role: str, name: str, session: Session, response: Response) -> dict:
    key, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=12)
    session.add(BrowserSession(id=key, subject=subject, csrf=csrf, expires_at=expires))
    session.commit()
    token = jwt.encode({"sub": subject, "role": role, "jti": key, "exp": expires}, JWT_SECRET, algorithm="HS256")
    response.set_cookie(COOKIE_NAME, token, httponly=True, secure=COOKIE_SECURE, samesite="lax", max_age=43200, path="/")
    response.headers["Cache-Control"] = "no-store"
    return {"access_token": token, "token_type": "bearer", "name": name, "sdu_id": subject if role != "guest" else None, "role": role, "csrf_token": csrf}


Identity = Annotated[dict, Depends(current_identity)]


def admin_only(identity: Identity) -> dict:
    if identity.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator role required")
    return identity


AdminIdentity = Annotated[dict, Depends(admin_only)]


DEMO_USERS = {
    "240103049": "Yerassyl",
    "240103050": "Daulet",
    "240103051": "Omar",
    "240103052": "Aitore",
    "240103053": "Aidyn",
    "240000001": "Dr. Ayan",
    "240000002": "Campus Admin",
}
DEMO_PASSWORD = "Campus123!"

LOCATION_SEEDS = [
    ("Main Entrance", "Entrance", "Block C", "Ground floor", .72, .76, "entrance c,main door"),
    ("Library", "Study", "Block B", "1st floor", .49, .88, "books,reading room"),
    ("Food Court", "Food", "Block F", "1st floor", .74, .33, "cafeteria,canteen,eat,coffee"),
    ("Room 317", "Classroom", "Block F", "3rd floor", .43, .38, "317,f317"),
    ("Student Service Centre", "Office", "Block D", "1st floor", .51, .61, "ssc,student office"),
    ("Medical Point", "Health", "Block H", "1st floor", .44, .18, "doctor,clinic,first aid"),
    ("Printer — Engineering", "Printer", "Block F", "2nd floor", .31, .34, "copy,printing"),
    ("Accessible Restroom", "Restroom", "Block E", "1st floor", .48, .47, "toilet,wc"),
    ("ATM", "Finance", "Block G", "1st floor", .26, .23, "cash,bank"),
    ("Parking Entrance", "Parking", "Block H", "Outside", .80, .15, "car park,park"),
    ("Teacher Office 215", "Office", "Block D", "2nd floor", .39, .57, "office hours,teacher"),
    ("Wi-Fi Lounge", "Service", "Block C", "1st floor", .62, .78, "internet,lounge"),
]


NEW_COLUMNS = {
    "location": [("step_free_access", "VARCHAR NOT NULL DEFAULT 'Not verified'")],
    "announcement": [("starts_at", "TIMESTAMP"), ("ends_at", "TIMESTAMP")],
    "inaccuracyreport": [("kind", "VARCHAR NOT NULL DEFAULT 'location'"), ("edge_a", "VARCHAR"), ("edge_b", "VARCHAR"),
                         ("route_start_id", "INTEGER"), ("route_destination_id", "INTEGER"),
                         ("resolution_note", "VARCHAR NOT NULL DEFAULT ''"), ("updated_at", "TIMESTAMP"),
                         ("reporter_unread", "BOOLEAN NOT NULL DEFAULT FALSE")],
    "pathstatus": [("reopens_at", "TIMESTAMP")],
}


def seed_database() -> None:
    SQLModel.metadata.create_all(engine)
    # create_all does not add columns to existing tables, so add the newer ones in place.
    with engine.begin() as connection:
        for table, columns in NEW_COLUMNS.items():
            existing = {column["name"] for column in inspect(connection).get_columns(table)}
            for name, definition in columns:
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
    with Session(engine) as session:
        if session.exec(select(RoleOverride)).first() is None:
            session.add_all([
                RoleOverride(email="240000001@sdu.edu.kz", role="teacher"),
                RoleOverride(email="240000002@sdu.edu.kz", role="admin"),
            ])
        for sdu_id, full_name in DEMO_USERS.items():
            email = f"{sdu_id}@sdu.edu.kz"
            role = "teacher" if sdu_id == "240000001" else "admin" if sdu_id == "240000002" else "student"
            user = session.exec(select(User).where(User.email == email)).first()
            if user is None:
                user = User(full_name=full_name, email=email, role=role)
                session.add(user)
                session.flush()
            account = session.exec(select(AuthAccount).where(AuthAccount.sdu_id == sdu_id)).first()
            if account is None:
                session.add(AuthAccount(sdu_id=sdu_id, password_hash=hash_password(DEMO_PASSWORD), user_id=user.id))
        if session.exec(select(Location)).first() is None:
            for name, category, block, floor, x, y, aliases in LOCATION_SEEDS:
                hours = "08:00–22:00" if name == "Library" else "08:00–18:00"
                session.add(Location(name=name, category=category, block=block, floor=floor, x=x, y=y, aliases=aliases, opening_hours=hours))
        if session.exec(select(Announcement)).first() is None:
            session.add_all([
                Announcement(title="Library extended hours", body="Open until 22:00 during assessment week.", location_id=2),
                Announcement(title="Career fair", body="Meet employers in the main atrium on Friday at 11:00.", location_id=1),
                Announcement(title="Block F printer maintenance", body="Use the printer in Block D until 14:00.", location_id=7),
            ])
        if session.exec(select(CampusClass)).first() is None:
            for sdu_id in DEMO_USERS:
                email = f"{sdu_id}@sdu.edu.kz"
                session.add(CampusClass(owner_email=email, course="Project Management", room="317", starts_at="10:30", location_id=4, kind="teacher" if email == "240000001@sdu.edu.kz" else "student"))
        # Import confirmed map records once; preserve admin edits on later starts.
        for record in MAP_LOCATIONS.values():
            marker = MAP_IMPORT_MARKER
            item = session.get(Location, record['id'])
            if item is not None and marker in item.aliases:
                continue
            if item is None:
                item = Location(id=record['id'], name=record['name'], category=record['category'],
                                block=record['block'], floor=record['floor'], x=record['x'], y=record['y'])
            for field in ('name', 'category', 'block', 'floor', 'x', 'y', 'opening_hours', 'contact', 'accessible'):
                setattr(item, field, record[field])
            item.aliases = record['aliases'] + ',' + marker
            session.add(item)
        if not session.get(DataMigration, "web-sample-schedule-v1"):
            room_ids = [p for p in MAP_LOCATIONS.values() if p['map_key'] in {'d201', 'f102', 'h203'}]
            for user in session.exec(select(User)).all():
                if user.email.split('@')[0] not in DEMO_USERS:
                    continue
                for day in range(1, 8):
                    for index, room in enumerate(room_ids):
                        start = (datetime.now(TZ) + timedelta(days=day)).replace(hour=9+index*2, minute=30, second=0, microsecond=0)
                        session.add(SampleLesson(user_id=user.id, course=["Project Management", "Software Engineering", "Academic English"][index], starts_at=start.astimezone(timezone.utc), location_id=room['id'], room=room['name'], kind="teacher" if user.role == "teacher" else "student"))
            session.add(DataMigration(key="web-sample-schedule-v1"))
        session.commit()


app = FastAPI(title="SDU Campus Assistant API", version="1.0.0", description="Course-project API for the map-first SDU campus assistant.")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True,
                   allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"])


@app.middleware("http")
async def browser_origin_check(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        same_site = origin and urlsplit(origin).netloc == request.headers.get("host")
        if origin and origin not in ALLOWED_ORIGINS and not same_site:
            return JSONResponse({"detail": "Origin is not allowed"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    # When served under /api (app.server), the mount prefix is in root_path.
    path = request.url.path.removeprefix(request.scope.get("root_path", ""))
    if path.startswith(("/auth", "/users", "/admin", "/students", "/teachers")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/auth/csrf", tags=["Authentication"])
def csrf_token(request: Request, session: DbSession):
    identity = resolve_identity(request, session)
    record = session.get(BrowserSession, identity.get("jti", ""))
    return {"csrf_token": record.csrf if record else None}


@app.post("/auth/logout", tags=["Authentication"])
def logout(identity: Identity, session: DbSession, response: Response):
    record = session.get(BrowserSession, identity.get("jti", ""))
    if record:
        record.revoked = True
        session.add(record)
        session.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"logged_out": True}


@app.on_event("startup")
def startup() -> None:
    seed_database()


@app.get("/health", tags=["System"])
def health() -> dict:
    return {"status": "ok", "database": DATABASE_URL.split(":", 1)[0]}


def adopt_guest_reports(request: Request, session: Session, sdu_id: str) -> None:
    """Move reports made in this browser's guest session to the account that just signed in."""
    try:
        identity = jwt.decode(request.cookies.get(COOKIE_NAME, ""), JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return
    if identity.get("role") != "guest" or not session.exec(select(GuestSession).where(GuestSession.session_key == identity["sub"])).first():
        return
    for report in session.exec(select(InaccuracyReport).where(InaccuracyReport.author == identity["sub"])).all():
        report.author = sdu_id
    session.commit()


@app.post("/auth/register", status_code=201, tags=["Authentication"])
def register(body: RegisterRequest, request: Request, session: DbSession, response: Response) -> dict:
    sdu_id = normalize_sdu_id(body.sdu_id)
    full_name = body.full_name.strip()
    if len(full_name) < 2:
        raise HTTPException(status_code=422, detail="Enter your full name")
    if session.exec(select(AuthAccount).where(AuthAccount.sdu_id == sdu_id)).first():
        raise HTTPException(status_code=409, detail="This SDU ID is already registered")
    email = f"{sdu_id}@sdu.edu.kz"
    role = "student"
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        user = User(full_name=full_name, email=email, role=role)
        session.add(user)
        session.flush()
    else:
        user.full_name = full_name
        user.role = "student"
    session.add(AuthAccount(sdu_id=sdu_id, password_hash=hash_password(body.password), user_id=user.id))
    session.commit()
    adopt_guest_reports(request, session, sdu_id)
    return issue_session(sdu_id, role, user.full_name, session, response)


@app.post("/auth/login", tags=["Authentication"])
def login(body: LoginRequest, request: Request, session: DbSession, response: Response) -> dict:
    sdu_id = normalize_sdu_id(body.sdu_id)
    account = session.exec(select(AuthAccount).where(AuthAccount.sdu_id == sdu_id)).first()
    if account is None or not verify_password(body.password, account.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect ID or password")
    user = session.get(User, account.user_id)
    if user is None or not user.active:
        raise HTTPException(status_code=403, detail="This account is unavailable")
    adopt_guest_reports(request, session, sdu_id)
    return issue_session(sdu_id, user.role, user.full_name, session, response)


@app.post("/auth/guest", tags=["Authentication"])
def guest(session: DbSession, response: Response) -> dict:
    key = str(uuid4())
    session.add(GuestSession(session_key=key))
    session.commit()
    return issue_session(key, "guest", "Guest", session, response)


@app.get("/users/me", tags=["Users"])
def me(identity: Identity, session: DbSession) -> dict:
    user = user_for_identity(identity, session)
    if user:
        return {**user.model_dump(), "sdu_id": user.email.split("@", 1)[0]}
    return {"name": "Campus Visitor", "role": "guest", "session": identity["sub"]}


def saved_avoid_stairs(identity: dict, session: Session) -> bool | None:
    """The saved step-free preference for an account or guest session; None when nothing can be saved."""
    user = user_for_identity(identity, session)
    if user:
        preference = session.exec(select(Preference).where(Preference.user_id == user.id)).first()
        return preference.accessible_routes if preference else False
    if identity.get("role") == "guest":
        preference = session.get(GuestPreference, identity["sub"])
        return preference.accessible_routes if preference else False
    return None


@app.get("/users/me/preferences", tags=["Users"])
def get_preferences(identity: Identity, session: DbSession) -> dict:
    value = saved_avoid_stairs(identity, session)
    if value is None:
        raise HTTPException(status_code=403, detail="Sign in or continue as a guest to save preferences")
    return {"accessible_routes": value, "saved_for": "guest_session" if identity.get("role") == "guest" else "account"}


@app.put("/users/me/preferences", tags=["Users"])
def update_preferences(body: PreferenceRequest, identity: Identity, session: DbSession) -> dict:
    user = user_for_identity(identity, session)
    if user:
        preference = session.exec(select(Preference).where(Preference.user_id == user.id)).first()
        if preference is None:
            preference = Preference(user_id=user.id)
    elif identity.get("role") == "guest":
        preference = session.get(GuestPreference, identity["sub"]) or GuestPreference(session_key=identity["sub"])
    else:
        raise HTTPException(status_code=403, detail="Sign in or continue as a guest to save preferences")
    preference.accessible_routes = body.accessible_routes
    session.add(preference)
    session.commit()
    return {"accessible_routes": preference.accessible_routes, "saved_for": "account" if user else "guest_session"}


@app.get("/locations", response_model=list[Location], tags=["Campus"])
def locations(session: DbSession, category: str | None = None) -> list[Location]:
    statement = select(Location).where(Location.id.notin_(RETIRED_LOCATION_IDS))
    if category:
        statement = statement.where(Location.category == category)
    return list(session.exec(statement).all())


def current_path_rows(session: Session) -> list[PathStatus]:
    """Active path decisions whose automatic reopening time has not passed."""
    now = datetime.now(timezone.utc)
    rows = session.exec(select(PathStatus).where(PathStatus.active == True)).all()  # noqa: E712
    return [row for row in rows if not row.reopens_at or as_utc(row.reopens_at) > now]


def active_path_status(session: Session) -> dict:
    """Admin path decisions by connection; a closure outranks a not-step-free mark."""
    states = {}
    for row in current_path_rows(session):
        key = edge_key(row.edge_a, row.edge_b)
        if states.get(key) != "closed":
            states[key] = row.state
    return states


def live_campus(session: Session) -> dict:
    # Use current database metadata; preserve explicit graph attachments and geometry.
    live = {item.id: item for item in session.exec(select(Location)).all()}
    return {**CAMPUS_MAP, "places": [{**p, **(live[p['id']].model_dump() if p['id'] in live else {})} for p in CAMPUS_MAP['places']]}


@app.get('/campus-map', tags=['Campus'])
def campus_map(session: DbSession) -> dict:
    campus = live_campus(session)
    places = [{**p, "step_free_access": campus["places"][i].get("step_free_access", "Not verified")}
              for i, p in enumerate(CAMPUS_MAP["places"])]
    return {**CAMPUS_MAP, "places": places, "network": network(CAMPUS_MAP, active_path_status(session))}


OPEN_REPORT_STATUSES = ("new", "reviewing")


@app.get("/paths/status", tags=["Campus"])
def paths_status(session: DbSession) -> list[dict]:
    """Connections that are closed, not step-free or already reported, so people don't report them twice."""
    states = active_path_status(session)
    counts = {}
    for report in session.exec(select(InaccuracyReport).where(InaccuracyReport.kind == "path",
                                                              InaccuracyReport.status.in_(OPEN_REPORT_STATUSES))).all():
        if report.edge_a and report.edge_b:
            key = edge_key(report.edge_a, report.edge_b)
            counts[key] = counts.get(key, 0) + 1
    return [{"a": key[0], "b": key[1], "state": states.get(key), "open_reports": counts.get(key, 0)}
            for key in sorted(set(states) | set(counts))]


@app.get("/locations/{location_id}/nearby-paths", tags=["Campus"])
def nearby_paths(location_id: int) -> list[dict]:
    """Corridors, stairs and lifts around a place, so a blocked path can be reported without planning a route."""
    place = MAP_LOCATIONS.get(location_id)
    if not place or place.get('access', 'public') != 'public':
        return []
    return nearby_connections(CAMPUS_MAP, place['map_key'])


@app.get("/locations/{location_id}", response_model=Location, tags=["Campus"])
def location(location_id: int, session: DbSession) -> Location:
    item = session.get(Location, location_id)
    if not item:
        raise HTTPException(status_code=404, detail="Location not found")
    return item


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def ranked_locations(q: str, session: Session) -> list[Location]:
    needle = normalized(q)
    if not needle:
        return []
    ranked = []
    for item in locations(session):
        name = normalized(item.name)
        synonyms = {"Medical Point": "doctor,clinic,first aid,sick,medical", "Library": "books,reading,study", "Print & Stationery": "printing,printer,photocopy,copy"}.get(item.name, "")
        terms = [*[normalized(alias) for alias in synonyms.split(',') if alias], name, *[normalized(alias) for alias in item.aliases.split(',') if not alias.startswith('[')]]
        score = max([1 if needle == term else .88 if needle in term else SequenceMatcher(None, needle, term).ratio() * .8 for term in terms if term] or [0])
        if needle in normalized(item.category) or needle in normalized(item.block):
            score = max(score, .72)
        if score >= .62:
            ranked.append((score + (.05 if name == needle else 0), item))
    return [item for _, item in sorted(ranked, key=lambda pair: (-pair[0], pair[1].name))][:30]


@app.get("/search", response_model=list[Location], tags=["Campus"])
def search_locations(session: DbSession, q: str = Query(min_length=1, max_length=200), actor: str = "public") -> list[Location]:
    results = ranked_locations(q, session)
    session.add(SearchLog(actor="public", query=q.strip().lower()))
    session.commit()
    for item in results:
        session.refresh(item)
    return results


@app.get("/services", response_model=list[Location], tags=["Campus"])
def services(session: DbSession) -> list[Location]:
    return [item for item in locations(session) if item.category != 'Classroom']


def announcement_state(item: Announcement, now: datetime) -> str:
    if item.starts_at and as_utc(item.starts_at) > now:
        return "scheduled"
    if item.ends_at and as_utc(item.ends_at) <= now:
        return "expired"
    return "showing"


def shown_from(item: Announcement) -> datetime:
    return as_utc(item.starts_at or item.published_at)


def showing_announcements(session: Session, location_id: int | None = None) -> list[Announcement]:
    now = datetime.now(timezone.utc)
    statement = select(Announcement)
    if location_id is not None:
        statement = statement.where(Announcement.location_id == location_id)
    rows = [item for item in session.exec(statement).all() if announcement_state(item, now) == "showing"]
    return sorted(rows, key=shown_from, reverse=True)


@app.get("/announcements", response_model=list[Announcement], tags=["Campus"])
def list_announcements(session: DbSession, location_id: int | None = None) -> list[Announcement]:
    """Announcements currently showing: started (or unscheduled) and not yet ended."""
    return showing_announcements(session, location_id)


@app.get("/routes", tags=["Navigation"])
def get_route(request: Request, session: DbSession, destination: int, start: int = 1, accessible: bool = False) -> dict:
    identity = resolve_identity(request, session, required=False)
    saved = saved_avoid_stairs(identity, session) if identity else None
    return route_for_user(session, start, destination, accessible if saved is None else saved)


def route_for_user(session: Session, start: int, destination: int, accessible: bool = False) -> dict:
    route = draft_route(live_campus(session), start, destination, accessible, active_path_status(session))
    return {**route, "start_location_id": start, "destination_location_id": destination}


def lessons_for(identity: dict, session: Session) -> list[SampleLesson]:
    user = user_for_identity(identity, session)
    if not user:
        raise HTTPException(403, "Registered account required")
    return list(session.exec(select(SampleLesson).where(SampleLesson.user_id == user.id).order_by(SampleLesson.starts_at)).all())


def upcoming_lesson(identity: dict, session: Session, now: datetime | None = None) -> SampleLesson | None:
    now = as_utc(now or datetime.now(TZ))
    return next((lesson for lesson in lessons_for(identity, session) if as_utc(lesson.starts_at) >= now), None)


@app.get("/assistant/status", tags=["Assistant"])
def assistant_status():
    config = ai_assistant.settings()
    return {"configured": bool(config.key), "engine": "openrouter" if config.key else "rules",
            "model": config.model if config.key else None}


@app.post("/assistant/query", tags=["Assistant"])
def assistant(body: AssistantRequest, request: Request, session: DbSession) -> dict:
    identity = resolve_identity(request, session, required=False)
    actor = identity['sub'] if identity else "public"
    if not body.selection_id and (not body.question.strip() or len(body.question) > 500):
        raise HTTPException(422, "Ask a campus question of up to 500 characters")
    conversation = None
    if body.conversation_id:
        conversation = session.get(AssistantConversation, body.conversation_id)
        if not conversation or conversation.actor != actor:
            raise HTTPException(404, "Conversation not found. Start a new chat.")
        if as_utc(conversation.expires_at) <= datetime.now(timezone.utc):
            raise HTTPException(410, "This chat has expired. Start a new chat.")
    config = ai_assistant.settings()
    answer = (assistant_scope.response("out_of_scope")
              if body.selection_id is None and assistant_scope.clearly_unrelated(body.question) else None)
    if answer is not None:
        answer["engine"] = "rules"
    reason = None
    if answer is None and config.key and body.selection_id is None:
        try:
            ai_assistant.check_rate(actor, request.client.host if request.client else "local", config.requests_per_minute)
            answer = openrouter_answer(body.question, identity, session, conversation, config)
            answer.update(engine="openrouter", model=config.model)
        except ai_assistant.AIUnavailable as exc:
            reason = exc.reason
    if answer is None:
        answer = rule_assistant(body, identity, session)
        answer["engine"] = "rules"
        if reason:
            answer["fallback_reason"] = reason
    if config.key or conversation:
        if conversation is None:
            conversation = AssistantConversation(id=secrets.token_urlsafe(24), actor=actor,
                         expires_at=datetime.now(timezone.utc)+timedelta(hours=12))
        history = json.loads(conversation.messages_json)
        question = body.question or "Selected " + str(body.selection_id)
        ids = [p.id for p in answer.get('choices', [])]
        if answer.get('location'):
            ids.append(answer['location'].id)
        history.extend([{"role": "user", "content": question}, {"role": "assistant", "content": json.dumps(
            {"answer": answer['answer'], "location_ids": ids}, ensure_ascii=False)}])
        conversation.messages_json = json.dumps(history[-12:], ensure_ascii=False)
        conversation_id = conversation.id
        session.add(conversation)
        # Serialize models before commit expires SQLModel fields.
        serialized = json.loads(json.dumps(answer, default=lambda obj: obj.model_dump(mode='json') if isinstance(obj, SQLModel) else str(obj)))
        session.commit()
        return {**serialized, "conversation_id": conversation_id}
    return answer


def openrouter_answer(question: str, identity: dict | None, session: Session,
                      conversation: AssistantConversation | None, config: ai_assistant.Settings) -> dict:
    observed: dict[int, Location] = {}
    routes: list[dict] = []
    evidence = []
    tool_results = []
    searched_queries = []

    def record(item: Location) -> dict:
        observed[item.id] = item
        metadata = MAP_LOCATIONS.get(item.id, {})
        return {"id": item.id, "name": item.name, "category": item.category, "block": item.block,
                "floor": item.floor, "opening_hours": item.opening_hours, "contact": item.contact,
                "mapped": metadata.get('has_position', False), "notes": metadata.get('notes', ''),
                "accessibility": "Unverified"}

    def read_location(location_id: int) -> Location | None:
        if type(location_id) is not int or location_id in RETIRED_LOCATION_IDS:
            return None
        metadata = MAP_LOCATIONS.get(location_id, {})
        if metadata.get('access', 'public') != 'public':
            return None
        return session.get(Location, location_id)

    def execute(name: str, args: dict) -> dict:
        result = execute_tool(name, args)
        tool_results.append((name, result))
        return result

    def execute_tool(name: str, args: dict) -> dict:
        schema = next((tool['function']['parameters'] for tool in ai_assistant.TOOLS if tool['function']['name'] == name), None)
        if not schema or set(args) != set(schema['required']):
            raise ValueError('Unsupported tool or arguments')
        for key, value in args.items():
            expected = schema['properties'][key]['type']
            if expected == 'integer' and type(value) is not int or expected == 'string' and (not isinstance(value, str) or not value.strip() or len(value) > 200):
                raise ValueError('Invalid arguments')
        evidence.append(name)
        if name == 'search_campus':
            searched_queries.append(args['query'].strip().lower())
            matches = ranked_locations(args['query'], session)
            exact = [item for item in matches if normalized(item.name) == normalized(args['query'])]
            matches = exact if len(exact) == 1 else matches[:8]
            return {"locations": [record(p) for p in matches if read_location(p.id)], "ambiguous": len(matches) > 1}
        if name == 'get_location':
            item = read_location(args['location_id'])
            return {"location": record(item)} if item else {"error": "Location unavailable or restricted"}
        if name in {'get_my_profile', 'get_my_saved_places', 'get_my_preferences', 'get_my_schedule', 'get_my_reports'}:
            user = user_for_identity(identity, session) if identity else None
            if not user:
                return {"status": "login_required", "message": "You are using guest mode. Sign in for your personal account information."}
            if name == 'get_my_profile':
                account = session.exec(select(AuthAccount).where(AuthAccount.user_id == user.id)).first()
                return {"full_name": user.full_name, "email": user.email, "sdu_id": account.sdu_id if account else None,
                        "faculty": user.faculty, "role": user.role, "source": "Stored app profile; no university-system integration"}
            if name == 'get_my_preferences':
                return {"avoid_stairs": saved_avoid_stairs(identity, session), "accessibility": "Routes remain unverified"}
            if name == 'get_my_saved_places':
                saved = session.exec(select(Favorite).where(Favorite.user_id == user.id)).all()
                return {"locations": [record(item) for favorite in saved if (item := read_location(favorite.location_id))]}
            if name == 'get_my_schedule':
                lessons = lessons_for(identity, session)
                return {"sample": True, "timezone": "Asia/Almaty", "truncated": len(lessons) > 30,
                        "lessons": [{"course": lesson.course, "room": lesson.room, "kind": lesson.kind,
                            "starts_at": as_utc(lesson.starts_at).astimezone(TZ).isoformat(),
                            "location": record(item) if lesson.location_id and (item := read_location(lesson.location_id)) else None}
                            for lesson in lessons[:30]]}
            reports = session.exec(select(InaccuracyReport).where(InaccuracyReport.author == identity['sub'])
                                   .order_by(InaccuracyReport.created_at.desc()).limit(10)).all()
            return {"reports": [{"message": r.message, "status": r.status, "created_at": r.created_at.isoformat(),
                      "kind": r.kind, "resolution_note": r.resolution_note,
                      "location": record(item) if r.location_id and (item := read_location(r.location_id)) else None} for r in reports]}
        if name == 'get_next_class':
            if not identity or identity['role'] == 'guest':
                return {"status": "login_required", "message": "Log in for your personal sample schedule"}
            lesson = upcoming_lesson(identity, session)
            if not lesson:
                return {"status": "empty", "sample": True, "timezone": "Asia/Almaty"}
            item = read_location(lesson.location_id) if lesson.location_id else None
            return {"sample": True, "course": lesson.course, "room": lesson.room,
                    "starts_at": as_utc(lesson.starts_at).astimezone(TZ).isoformat(), "timezone": "Asia/Almaty",
                    "location": record(item) if item else None}
        if name == 'get_campus_updates':
            updates = showing_announcements(session)[:5]
            return {"updates": [{"title": n.title, "body": n.body, "published_at": n.published_at.isoformat(),
                     "location": record(item) if (item := read_location(n.location_id)) else None}
                    for n in updates], "note": "Seeded announcements are sample data"}
        if name == 'plan_route':
            start, target = read_location(args['start_location_id']), read_location(args['destination_location_id'])
            if not start or not target:
                return {"status": "unmapped", "message": "Start or destination unavailable or restricted"}
            record(start); record(target)
            path = route_for_user(session, start.id, target.id, bool(identity and saved_avoid_stairs(identity, session)))
            routes.append(path)
            return {k: v for k, v in path.items() if k not in {'points', 'node_path', 'segments'}}
        raise ValueError('Unsupported tool')

    def present(args: dict) -> dict:
        intent = args.pop("_intent", None)
        if intent not in assistant_scope.INTENTS:
            raise ai_assistant.AIUnavailable('invalid_response')
        if set(args) != {'answer', 'location_ids', 'needs_clarification', 'route_requested'} or not evidence:
            raise ai_assistant.AIUnavailable('invalid_response')
        ids = args['location_ids']
        if (not isinstance(args['answer'], str) or not args['answer'].strip() or len(args['answer']) > 1800
            or not isinstance(ids, list) or len(ids) > 8 or any(type(i) is not int or i not in observed for i in ids)
            or type(args['needs_clarification']) is not bool or type(args['route_requested']) is not bool):
            raise ai_assistant.AIUnavailable('invalid_response')
        ids = list(dict.fromkeys(ids))
        selected = [observed[i] for i in ids]
        clarification = args['needs_clarification'] and len(selected) > 1
        response = {"answer": assistant_answers.render(intent, [record(item) for item in selected], clarification, routes, tool_results), "location": selected[0] if selected and not clarification else None,
                    "locations": selected if not clarification else [], "choices": selected if clarification else [],
                    "needs_clarification": clarification}
        if clarification:
            context = AssistantContext(id=secrets.token_urlsafe(24), actor=identity['sub'] if identity else 'public',
                choices_json=json.dumps(ids), route_intent=args['route_requested'],
                expires_at=datetime.now(timezone.utc)+timedelta(minutes=30))
            session.add(context)
            session.flush()
            response['context_id'] = context.id
        if routes and not clarification:
            response['route'] = routes[-1]
            target = observed.get(routes[-1]['destination_location_id'])
            response['location'] = target
        return response

    history = json.loads(conversation.messages_json) if conversation else []
    try:
        return ai_assistant.run(question, history, execute, present, config)
    finally:
        # Do not hold a database writer while waiting on a remote model response.
        for query in searched_queries:
            session.add(SearchLog(actor='assistant', query=query))


def rule_assistant(body: AssistantRequest, identity: dict | None, session: Session) -> dict:
    actor = identity['sub'] if identity else 'public'
    q = body.question.lower().strip()
    if body.selection_id is None and assistant_scope.clearly_unrelated(body.question):
        return assistant_scope.response("out_of_scope")
    def result(answer, item=None, **extra):
        return {"answer": answer, "location": item, "needs_clarification": False, "choices": [], **extra}
    if body.selection_id is not None:
        context = session.get(AssistantContext, body.context_id or "")
        if not context or context.actor != actor or as_utc(context.expires_at) < datetime.now(timezone.utc) or body.selection_id not in json.loads(context.choices_json):
            raise HTTPException(422, "This choice has expired. Please ask again.")
        item = session.get(Location, body.selection_id)
        return result(f"Selected {item.name}. Open it on the map or plan a route from your chosen start.", item, action="route" if context.route_intent else "map")
    if not q or len(q) > 500:
        raise HTTPException(422, "Ask a campus question of up to 500 characters")
    if not assistant_scope.fallback_allowed(q):
        # Bare room codes, names, and aliases remain valid searches.
        matches = ranked_locations(q, session)
        if not matches:
            return assistant_scope.response("clarify")
        exact = [item for item in matches if normalized(q) in {
            normalized(item.name), normalized(item.category),
            *[normalized(alias) for alias in item.aliases.split(",") if not alias.startswith("[")],
        }]
        if not exact:
            return assistant_scope.response("clarify")
    if any(term in q for term in ["my name", "who am i", "my profile", "my account", "about me"]):
        user = user_for_identity(identity, session) if identity else None
        if not user:
            return result("You are using guest mode. Sign in so I can access your stored profile and personal campus information.")
        return result(f"Your name is {user.full_name}. Your account role is {user.role}, and your faculty is {user.faculty}.")
    if any(term in q for term in ["next class", "next lesson", "my class", "my lesson", "next lecture", "where do i go next"]):
        if not identity or identity['role'] == 'guest':
            return result("Log in to see your personal sample timetable.")
        lesson = upcoming_lesson(identity, session)
        if not lesson:
            return result("There are no upcoming lessons in your stored sample schedule (Asia/Almaty).")
        item = session.get(Location, lesson.location_id) if lesson.location_id else None
        return result(f"Sample schedule: {lesson.course}, {as_utc(lesson.starts_at).astimezone(TZ).strftime('%d %b, %H:%M')} Asia/Almaty, {lesson.room}." + (" This room has no mapped position." if not item or not MAP_LOCATIONS.get(item.id, {}).get('has_position') else ""), item, lesson=lesson.model_dump())
    if 'park' in q:
        return result("Parking locations are not confirmed in the campus catalogue.")
    needs = [(('sick', 'ill', 'medical', 'doctor', 'first aid', 'unwell', 'hurt'), 'Medical Point', 'For health support, the catalogue lists'),
             (('print', 'photocopy', 'stationery'), 'Print & Stationery', 'For printing and stationery, the catalogue lists'),
             (('study', 'books', 'library', 'libary', 'read'), 'Library', 'For books and study space, the catalogue lists'),
             (('hungry', 'eat', 'food', 'lunch', 'coffee', 'canteen'), 'Canteen', 'For food, the catalogue lists')]
    explanation = 'I found'
    query = q
    for terms, service, reason in needs:
        if any(re.search(r'\b' + re.escape(term) + r'\w*\b', q) for term in terms):
            query, explanation = service, reason
            break
    if query == q:
        query = re.sub(r"\b(where|is|are|the|please|find|show|me|how|do|i|get|to|take|route|directions|room|can|you|a|in|on|campus)\b", " ", q).strip()
    room_match = re.search(r"\b([d-h])\s*(\d{3})\b", q)
    if room_match:
        query = ''.join(room_match.groups())
    matches = ranked_locations(query, session)
    if not matches:
        return result("I could not find confirmed catalogue data for that request. Try a room code, library, printing or medical point.")
    # Exact names/codes resolve immediately; broad categories and competing names need selectable choices.
    exact = [item for item in matches if normalized(item.name) == normalized(query)]
    if len(exact) == 1:
        matches = exact
    if len(matches) > 1:
        choices = matches[:8]
        context = AssistantContext(id=secrets.token_urlsafe(24), actor=actor, choices_json=json.dumps([item.id for item in choices]), route_intent=any(t in q for t in ['route', 'directions', 'get to']), expires_at=datetime.now(timezone.utc)+timedelta(minutes=30))
        session.add(context)
        session.commit()
        for choice in choices:
            session.refresh(choice)
        return result("I found several matches. Choose the place you mean.", needs_clarification=True, choices=choices, context_id=context.id)
    item = matches[0]
    answer = f"{explanation} {item.name}, {item.block}, {item.floor}."
    if any(t in q for t in ['hours', 'open', 'close']):
        answer += f" Hours: {item.opening_hours}."
    if any(t in q for t in ['contact', 'phone', 'call']):
        answer += f" Contact: {item.contact}."
    return result(answer, item)


@app.get("/students/me/timetable", response_model=list[SampleLesson], tags=["Schedules"])
def student_timetable(identity: Identity, session: DbSession):
    return lessons_for(identity, session)


@app.get("/students/me/next-class", response_model=SampleLesson | None, tags=["Schedules"])
def next_class(identity: Identity, session: DbSession):
    return upcoming_lesson(identity, session)


@app.get("/teachers/me/schedule", response_model=list[SampleLesson], tags=["Schedules"])
def teacher_schedule(identity: Identity, session: DbSession):
    if identity['role'] not in {'teacher', 'admin'}:
        raise HTTPException(403, "Teacher role required")
    return lessons_for(identity, session)


@app.get("/users/me/favorites", response_model=list[Location], tags=["Users"])
def favorites(identity: Identity, session: DbSession) -> list[Location]:
    user = user_for_identity(identity, session)
    if not user:
        raise HTTPException(403, "Registered account required")
    ids = [fav.location_id for fav in session.exec(select(Favorite).where(Favorite.user_id == user.id)).all()]
    return list(session.exec(select(Location).where(Location.id.in_(ids))).all()) if ids else []


@app.post("/users/me/favorites/{location_id}", status_code=201, tags=["Users"])
def add_favorite(location_id: int, identity: Identity, session: DbSession) -> dict:
    # SQLite has no SELECT FOR UPDATE. Reserve its writer before reading the count;
    # PostgreSQL uses the per-user row lock below instead.
    if session.bind.dialect.name == "sqlite":
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")
    user = user_for_identity(identity, session)
    if not user:
        raise HTTPException(status_code=403, detail="Registered account required")
    if not session.get(Location, location_id):
        raise HTTPException(status_code=404, detail="Location not found")
    # Serialize saves per account in PostgreSQL so concurrent requests cannot exceed 5.
    session.exec(select(User).where(User.id == user.id).with_for_update()).one()
    existing = session.exec(select(Favorite).where(Favorite.user_id == user.id, Favorite.location_id == location_id)).first()
    if not existing:
        saved = session.exec(select(Favorite).where(Favorite.user_id == user.id)).all()
        if len({item.location_id for item in saved}) >= 5:
            raise HTTPException(status_code=409, detail="You can save up to 5 places. Remove one before saving another.")
        session.add(Favorite(user_id=user.id, location_id=location_id))
        session.commit()
    return {"saved": True, "location_id": location_id}


@app.delete("/users/me/favorites/{location_id}", tags=["Users"])
def remove_favorite(location_id: int, identity: Identity, session: DbSession) -> dict:
    user = user_for_identity(identity, session)
    if not user:
        raise HTTPException(403, "Registered account required")
    existing = session.exec(select(Favorite).where(Favorite.user_id == user.id, Favorite.location_id == location_id)).all()
    for item in existing:
        session.delete(item)
    session.commit()
    return {"saved": False, "location_id": location_id}


REPORT_STATUSES = {"new", "reviewing", "resolved", "rejected"}
GRAPH_EDGES = {edge_key(e['a'], e['b']) for e in CAMPUS_MAP['routing']['edges']}


def same_problem(report: InaccuracyReport, other: InaccuracyReport) -> bool:
    if report.kind != other.kind:
        return False
    if report.kind == "path":
        return bool(report.edge_a and other.edge_a) and edge_key(report.edge_a, report.edge_b) == edge_key(other.edge_a, other.edge_b)
    return report.location_id is not None and report.location_id == other.location_id


def report_view(report: InaccuracyReport, session: Session, open_reports: list[InaccuracyReport] | None = None) -> dict:
    location = session.get(Location, report.location_id) if report.location_id else None
    closure = None
    if report.edge_a and report.edge_b:
        key = edge_key(report.edge_a, report.edge_b)
        current = [row for row in current_path_rows(session) if edge_key(row.edge_a, row.edge_b) == key]
        closure = {"id": current[-1].id, "state": current[-1].state,
                   "reopens_at": current[-1].reopens_at.isoformat() if current[-1].reopens_at else None} if current else None
    route = [session.get(Location, i) for i in (report.route_start_id, report.route_destination_id) if i]
    if open_reports is None:
        open_reports = session.exec(select(InaccuracyReport).where(InaccuracyReport.status.in_(OPEN_REPORT_STATUSES))).all()
    similar = [other.id for other in open_reports if other.id != report.id and same_problem(report, other)]
    return {**report.model_dump(), "location_name": location.name if location else None,
            "connection_label": connection_label(CAMPUS_MAP, report.edge_a, report.edge_b) if report.edge_a and report.edge_b else None,
            "route": " → ".join(item.name for item in route if item) or None, "path_status": closure,
            "similar_open": similar}


def tell_reporter(report: InaccuracyReport, status: str, note: str) -> None:
    report.status = status
    report.resolution_note = note
    report.updated_at = datetime.now(timezone.utc)
    report.reporter_unread = True


@app.post("/reports", status_code=201, tags=["Reports"])
def create_report(body: ReportRequest, identity: Identity, session: DbSession) -> dict:
    if not body.message.strip() or len(body.message) > 2000:
        raise HTTPException(422, "Describe the problem in 1–2000 characters")
    if body.kind not in {"location", "path"}:
        raise HTTPException(422, "Choose location information or a blocked path")
    if body.location_id is not None and not session.get(Location, body.location_id):
        raise HTTPException(404, "Location not found")
    if body.kind == "path" and (not body.edge_a or not body.edge_b or edge_key(body.edge_a, body.edge_b) not in GRAPH_EDGES):
        raise HTTPException(422, "Choose the part of the route that is blocked")
    if body.kind == "path" and active_path_status(session).get(edge_key(body.edge_a, body.edge_b)) == "closed":
        raise HTTPException(409, "This path is already closed, and routes go around it")
    if body.kind == "location" and body.location_id is None:
        raise HTTPException(422, "Choose the location to correct")
    report = InaccuracyReport(author=identity["sub"], location_id=body.location_id, message=body.message.strip(), kind=body.kind,
                              edge_a=body.edge_a if body.kind == "path" else None, edge_b=body.edge_b if body.kind == "path" else None,
                              route_start_id=body.route_start_id, route_destination_id=body.route_destination_id)
    session.add(report)
    session.commit()
    session.refresh(report)
    return report_view(report, session)


@app.get("/reports/me", tags=["Reports"])
def my_reports(identity: Identity, session: DbSession) -> list[dict]:
    rows = session.exec(select(InaccuracyReport).where(InaccuracyReport.author == identity["sub"])
                        .order_by(InaccuracyReport.created_at.desc())).all()
    return [report_view(report, session, []) for report in rows]


@app.post("/reports/me/seen", tags=["Reports"])
def mark_reports_seen(identity: Identity, session: DbSession) -> dict:
    rows = session.exec(select(InaccuracyReport).where(InaccuracyReport.author == identity["sub"],
                                                       InaccuracyReport.reporter_unread == True)).all()  # noqa: E712
    for report in rows:
        report.reporter_unread = False
    session.commit()
    return {"seen": len(rows)}


@app.post("/reports/{report_id}/withdraw", tags=["Reports"])
def withdraw_report(report_id: int, identity: Identity, session: DbSession) -> dict:
    report = session.get(InaccuracyReport, report_id)
    if not report or report.author != identity["sub"]:
        raise HTTPException(404, "Report not found")
    if report.status not in OPEN_REPORT_STATUSES:
        raise HTTPException(409, "Only reports that are still open can be withdrawn")
    report.status = "withdrawn"
    report.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(report)
    return report_view(report, session, [])


@app.get("/admin/users", response_model=list[User], tags=["Administration"])
def admin_users(_: AdminIdentity, session: DbSession) -> list[User]:
    return list(session.exec(select(User)).all())


@app.put("/admin/users/{user_id}/roles", response_model=User, tags=["Administration"])
def set_role(user_id: int, body: RoleRequest, _: AdminIdentity, session: DbSession) -> User:
    if body.role not in {"student", "teacher", "admin"}:
        raise HTTPException(status_code=422, detail="Unsupported role")
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = body.role
    override = session.exec(select(RoleOverride).where(RoleOverride.email == user.email)).first()
    if override:
        override.role = body.role
        session.add(override)
    else:
        session.add(RoleOverride(email=user.email, role=body.role, reason="Assigned by administrator"))
    session.commit()
    session.refresh(user)
    return user


@app.put("/admin/locations/{location_id}", response_model=Location, tags=["Administration"])
def edit_location(location_id: int, body: LocationDetailsRequest, _: AdminIdentity, session: DbSession) -> Location:
    item = session.get(Location, location_id)
    if not item:
        raise HTTPException(status_code=404, detail="Location not found")
    if body.step_free_access not in STEP_FREE_STATES:
        raise HTTPException(422, "Choose a valid step-free access status")
    if not body.name.strip():
        raise HTTPException(422, "Enter a name")
    aliases = [a.strip() for a in body.aliases.split(",") if a.strip() and a.strip() != MAP_IMPORT_MARKER]
    # Keep the import marker so later startups do not overwrite these edits with the map file.
    if MAP_IMPORT_MARKER in item.aliases:
        aliases.append(MAP_IMPORT_MARKER)
    report = session.get(InaccuracyReport, body.report_id) if body.report_id else None
    if body.report_id and (not report or report.kind != "location" or report.location_id != location_id):
        raise HTTPException(404, "Report about this location not found")
    if body.resolution_note is not None and len(body.resolution_note) > 1000:
        raise HTTPException(422, "Keep the message to 1000 characters")
    for key, value in body.model_dump(exclude={"report_id", "resolution_note"}).items():
        setattr(item, key, value.strip() if isinstance(value, str) else value)
    item.aliases = ",".join(aliases)
    if report:
        note = (body.resolution_note or "").strip() or f"We updated the details for {item.name}. Thanks for reporting it!"
        # Everyone who reported this place gets the answer, as with closed paths.
        for other in session.exec(select(InaccuracyReport).where(InaccuracyReport.kind == "location",
                                                                 InaccuracyReport.location_id == location_id,
                                                                 InaccuracyReport.status.in_(OPEN_REPORT_STATUSES))).all():
            tell_reporter(other, "resolved", note)
    session.commit()
    session.refresh(item)
    return item


@app.get("/admin/reports", tags=["Administration"])
def admin_reports(_: AdminIdentity, session: DbSession) -> list[dict]:
    rows = session.exec(select(InaccuracyReport).order_by(InaccuracyReport.created_at.desc())).all()
    open_reports = [report for report in rows if report.status in OPEN_REPORT_STATUSES]
    return [report_view(report, session, open_reports) for report in rows]


@app.put("/admin/reports/{report_id}", tags=["Administration"])
def update_report(report_id: int, body: ReportUpdateRequest, _: AdminIdentity, session: DbSession) -> dict:
    report = session.get(InaccuracyReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if body.status not in REPORT_STATUSES:
        raise HTTPException(422, "Choose a valid report status")
    if body.resolution_note is not None and len(body.resolution_note) > 1000:
        raise HTTPException(422, "Keep the update to 1000 characters")
    note = report.resolution_note if body.resolution_note is None else body.resolution_note.strip()
    if body.status != report.status or note != report.resolution_note:
        tell_reporter(report, body.status, note)
    session.commit()
    session.refresh(report)
    return report_view(report, session)


@app.get("/admin/path-status", tags=["Administration"])
def list_path_status(_: AdminIdentity, session: DbSession) -> list[dict]:
    rows = sorted(current_path_rows(session), key=lambda row: row.created_at, reverse=True)
    return [{**row.model_dump(), "label": connection_label(CAMPUS_MAP, row.edge_a, row.edge_b)} for row in rows]


@app.post("/admin/path-status", status_code=201, tags=["Administration"])
def set_path_status(body: PathStatusRequest, _: AdminIdentity, session: DbSession) -> dict:
    key = edge_key(body.edge_a, body.edge_b)
    if key not in GRAPH_EDGES:
        raise HTTPException(404, "Connection not found")
    if body.state not in {"closed", "not_step_free"}:
        raise HTTPException(422, "Choose closed or not step-free")
    if body.report_id and not session.get(InaccuracyReport, body.report_id):
        raise HTTPException(404, "Report not found")
    if body.reopens_at and (body.reopens_at.tzinfo is None or body.reopens_at <= datetime.now(timezone.utc)):
        raise HTTPException(422, "Choose a future reopening time with a timezone")
    for row in session.exec(select(PathStatus).where(PathStatus.active == True)).all():  # noqa: E712
        if edge_key(row.edge_a, row.edge_b) == key:
            row.active = False
    row = PathStatus(edge_a=key[0], edge_b=key[1], state=body.state, note=body.note.strip()[:1000],
                     report_id=body.report_id, reopens_at=body.reopens_at)
    session.add(row)
    until = f" until {as_utc(body.reopens_at).astimezone(TZ).strftime('%d %b, %H:%M')}" if body.reopens_at else ""
    note = (f"This path is now closed{until}, and routes go around it. Thanks for reporting it!" if body.state == "closed"
            else f"This path is now marked as not step-free{until}; step-free routes avoid it. Thanks for reporting it!")
    # Everyone who reported this same path gets the answer, not just the report the admin clicked.
    for report in session.exec(select(InaccuracyReport).where(InaccuracyReport.kind == "path",
                                                              InaccuracyReport.status.in_(OPEN_REPORT_STATUSES))).all():
        if report.edge_a and edge_key(report.edge_a, report.edge_b) == key:
            tell_reporter(report, "resolved", report.resolution_note or note)
    session.commit()
    session.refresh(row)
    return {**row.model_dump(), "label": connection_label(CAMPUS_MAP, row.edge_a, row.edge_b)}


@app.delete("/admin/path-status/{status_id}", tags=["Administration"])
def reopen_path(status_id: int, _: AdminIdentity, session: DbSession) -> dict:
    row = session.get(PathStatus, status_id)
    if not row or not row.active:
        raise HTTPException(404, "Path status not found")
    row.active = False
    session.commit()
    return {"reopened": True, "id": status_id}


@app.get("/admin/analytics/popular-searches", tags=["Administration"])
def popular_searches(_: AdminIdentity, session: DbSession) -> list[dict]:
    rows = session.exec(select(SearchLog.query, func.count(SearchLog.id)).group_by(SearchLog.query).order_by(func.count(SearchLog.id).desc(), SearchLog.query)).all()
    return [{"query": query, "count": count} for query, count in rows]


class AnnouncementRequest(BaseModel):
    title: str
    body: str
    location_id: int | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


def check_announcement(body: AnnouncementRequest, session: Session) -> None:
    if not body.title.strip() or not body.body.strip():
        raise HTTPException(422, "Title and message are required")
    if body.location_id is not None and not session.get(Location, body.location_id):
        raise HTTPException(404, "Location not found")
    if any(value and value.tzinfo is None for value in (body.starts_at, body.ends_at)):
        raise HTTPException(422, "Include a timezone; announcements use Asia/Almaty")
    if body.starts_at and body.ends_at and body.ends_at <= body.starts_at:
        raise HTTPException(422, "Show until must be after show from")


@app.get("/admin/announcements", tags=["Administration"])
def admin_announcements(_: AdminIdentity, session: DbSession) -> list[dict]:
    now = datetime.now(timezone.utc)
    rows = sorted(session.exec(select(Announcement)).all(), key=shown_from, reverse=True)
    return [{**item.model_dump(), "state": announcement_state(item, now)} for item in rows]


@app.delete("/admin/announcements/{item_id}", tags=["Administration"])
def delete_announcement(item_id: int, _: AdminIdentity, session: DbSession) -> dict:
    item = session.get(Announcement, item_id)
    if not item:
        raise HTTPException(404, "Announcement not found")
    session.delete(item)
    session.commit()
    return {"deleted": True, "id": item_id}


@app.post("/admin/announcements", response_model=Announcement, status_code=201, tags=["Administration"])
def create_announcement(body: AnnouncementRequest, _: AdminIdentity, session: DbSession):
    check_announcement(body, session)
    item = Announcement(**body.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@app.put("/admin/announcements/{item_id}", response_model=Announcement, tags=["Administration"])
def edit_announcement(item_id: int, body: AnnouncementRequest, _: AdminIdentity, session: DbSession):
    item = session.get(Announcement, item_id)
    if not item:
        raise HTTPException(404, "Announcement not found")
    check_announcement(body, session)
    for key, value in body.model_dump().items():
        setattr(item, key, value)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


class LessonRequest(BaseModel):
    course: str
    starts_at: datetime
    room: str
    location_id: int | None = None


def lesson_values(body: LessonRequest, session: Session) -> dict:
    if not body.course.strip() or not body.room.strip():
        raise HTTPException(422, "Course and room are required")
    if body.starts_at.tzinfo is None:
        raise HTTPException(422, "Include a timezone; schedules use Asia/Almaty")
    if body.location_id is not None and not session.get(Location, body.location_id):
        raise HTTPException(404, "Location not found")
    return {**body.model_dump(), "starts_at": body.starts_at.astimezone(timezone.utc)}


@app.post('/students/me/timetable', response_model=SampleLesson, status_code=201, tags=['Schedules'])
def add_lesson(body: LessonRequest, identity: Identity, session: DbSession):
    user = user_for_identity(identity, session)
    if not user:
        raise HTTPException(403, "Registered account required")
    item = SampleLesson(**lesson_values(body, session), user_id=user.id, kind='teacher' if user.role == 'teacher' else 'student')
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@app.put('/students/me/timetable/{lesson_id}', response_model=SampleLesson, tags=['Schedules'])
def edit_lesson(lesson_id: int, body: LessonRequest, identity: Identity, session: DbSession):
    user = user_for_identity(identity, session)
    if not user:
        raise HTTPException(403, "Registered account required")
    item = session.get(SampleLesson, lesson_id)
    if not item or item.user_id != user.id:
        raise HTTPException(404, "Lesson not found")
    for key, value in lesson_values(body, session).items():
        setattr(item, key, value)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item
