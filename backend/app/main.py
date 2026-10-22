from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import json
import zlib
from .routing import draft_route
from . import ai_assistant
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from difflib import SequenceMatcher
from typing import Annotated
from uuid import uuid4

import jwt
from fastapi import Depends, FastAPI, HTTPException, Query, status, Request, Response, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import or_, func, Column, DateTime
from sqlalchemy.types import TypeDecorator
from sqlmodel import Field, Session, SQLModel, create_engine, select

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sdu_campus.db")
JWT_SECRET = os.getenv("JWT_SECRET", "sdu-campus-course-demo-secret")
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
security = HTTPBearer(auto_error=False)
ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_NAME = "sdu_session"
TZ = ZoneInfo("Asia/Almaty")
CAMPUS_MAP = json.loads((Path(__file__).parent / 'data/campus.json').read_text())
MAP_LOCATIONS = {p['id']: p for p in CAMPUS_MAP['places']}
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


class InaccuracyReport(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    author: str
    location_id: int | None = None
    message: str
    status: str = Field(default="new", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


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


class AssistantRequest(BaseModel):
    question: str = ""
    conversation_id: str | None = None
    context_id: str | None = None
    selection_id: int | None = None


class RoleRequest(BaseModel):
    role: str


class StatusRequest(BaseModel):
    status: str


class PreferenceRequest(BaseModel):
    accessible_routes: bool


class LocationRequest(BaseModel):
    name: str
    category: str
    block: str
    floor: str
    x: float
    y: float
    opening_hours: str = "Not confirmed"
    contact: str = "Not confirmed"
    accessible: bool = True
    aliases: str = ""


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


def seed_database() -> None:
    SQLModel.metadata.create_all(engine)
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
            marker = '[campus-map-v1]'
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
        if origin and origin not in ALLOWED_ORIGINS and origin != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": "Origin is not allowed"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path.startswith(("/auth", "/users", "/admin", "/students", "/teachers")):
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


@app.post("/auth/register", status_code=201, tags=["Authentication"])
def register(body: RegisterRequest, session: DbSession, response: Response) -> dict:
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
    return issue_session(sdu_id, role, user.full_name, session, response)


@app.post("/auth/login", tags=["Authentication"])
def login(body: LoginRequest, session: DbSession, response: Response) -> dict:
    sdu_id = normalize_sdu_id(body.sdu_id)
    account = session.exec(select(AuthAccount).where(AuthAccount.sdu_id == sdu_id)).first()
    if account is None or not verify_password(body.password, account.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect ID or password")
    user = session.get(User, account.user_id)
    if user is None or not user.active:
        raise HTTPException(status_code=403, detail="This account is unavailable")
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


@app.get("/users/me/preferences", tags=["Users"])
def get_preferences(identity: Identity, session: DbSession) -> dict:
    user = user_for_identity(identity, session)
    if not user:
        raise HTTPException(status_code=403, detail="Registered account required")
    preference = session.exec(select(Preference).where(Preference.user_id == user.id)).first()
    if preference is None:
        preference = Preference(user_id=user.id)
        session.add(preference)
        session.commit()
        session.refresh(preference)
    return {"accessible_routes": preference.accessible_routes}


@app.put("/users/me/preferences", tags=["Users"])
def update_preferences(body: PreferenceRequest, identity: Identity, session: DbSession) -> dict:
    user = user_for_identity(identity, session)
    if not user:
        raise HTTPException(status_code=403, detail="Registered account required")
    preference = session.exec(select(Preference).where(Preference.user_id == user.id)).first()
    if preference is None:
        preference = Preference(user_id=user.id)
        session.add(preference)
    preference.accessible_routes = body.accessible_routes
    session.commit()
    return {"accessible_routes": preference.accessible_routes}


@app.get("/locations", response_model=list[Location], tags=["Campus"])
def locations(session: DbSession, category: str | None = None) -> list[Location]:
    statement = select(Location).where(Location.id.notin_(RETIRED_LOCATION_IDS))
    if category:
        statement = statement.where(Location.category == category)
    return list(session.exec(statement).all())


@app.get('/campus-map', tags=['Campus'])
def campus_map() -> dict:
    return CAMPUS_MAP


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


@app.get("/announcements", response_model=list[Announcement], tags=["Campus"])
def list_announcements(session: DbSession) -> list[Announcement]:
    return list(session.exec(select(Announcement).order_by(Announcement.published_at.desc())).all())


@app.get("/routes", tags=["Navigation"])
def get_route(request: Request, session: DbSession, destination: int, start: int = 1, accessible: bool = False) -> dict:
    identity = resolve_identity(request, session, required=False)
    user = user_for_identity(identity, session) if identity else None
    if user:
        pref = session.exec(select(Preference).where(Preference.user_id == user.id)).first()
        accessible = pref.accessible_routes if pref else False
    return route_for_user(session, start, destination, accessible)


def route_for_user(session: Session, start: int, destination: int, accessible: bool = False) -> dict:
    # Use current database metadata; preserve explicit graph attachments and geometry.
    campus = {**CAMPUS_MAP, "places": [{**p, **(session.get(Location, p['id']).model_dump() if session.get(Location, p['id']) else {})} for p in CAMPUS_MAP['places']]}
    return {**draft_route(campus, start, destination, accessible), "start_location_id": start, "destination_location_id": destination}


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
    answer = None
    reason = None
    if config.key and body.selection_id is None:
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
            updates = session.exec(select(Announcement).order_by(Announcement.published_at.desc()).limit(5)).all()
            return {"updates": [{"title": n.title, "body": n.body, "published_at": n.published_at.isoformat(),
                     "location": record(item) if (item := read_location(n.location_id)) else None}
                    for n in updates], "note": "Seeded announcements are sample data"}
        if name == 'plan_route':
            start, target = read_location(args['start_location_id']), read_location(args['destination_location_id'])
            if not start or not target:
                return {"status": "unmapped", "message": "Start or destination unavailable or restricted"}
            record(start); record(target)
            user = user_for_identity(identity, session) if identity else None
            pref = session.exec(select(Preference).where(Preference.user_id == user.id)).first() if user else None
            path = route_for_user(session, start.id, target.id, pref.accessible_routes if pref else False)
            routes.append(path)
            return {k: v for k, v in path.items() if k not in {'points', 'node_path', 'segments'}}
        raise ValueError('Unsupported tool')

    def present(args: dict) -> dict:
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
        response = {"answer": args['answer'].strip(), "location": selected[0] if selected and not clarification else None,
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


@app.post("/reports", response_model=InaccuracyReport, status_code=201, tags=["Reports"])
def create_report(body: ReportRequest, identity: Identity, session: DbSession) -> InaccuracyReport:
    if not user_for_identity(identity, session):
        raise HTTPException(403, "Registered account required")
    if not body.message.strip() or len(body.message) > 2000:
        raise HTTPException(422, "Describe the correction in 1–2000 characters")
    if body.location_id is not None and not session.get(Location, body.location_id):
        raise HTTPException(404, "Location not found")
    report = InaccuracyReport(author=identity["sub"], location_id=body.location_id, message=body.message)
    session.add(report)
    session.commit()
    session.refresh(report)
    return report


@app.get("/reports/me", response_model=list[InaccuracyReport], tags=["Reports"])
def my_reports(identity: Identity, session: DbSession) -> list[InaccuracyReport]:
    if not user_for_identity(identity, session):
        raise HTTPException(403, "Registered account required")
    return list(session.exec(select(InaccuracyReport).where(InaccuracyReport.author == identity["sub"])).all())


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


@app.post("/admin/locations", response_model=Location, status_code=201, tags=["Administration"])
def add_location(body: LocationRequest, _: AdminIdentity, session: DbSession) -> Location:
    item = Location(**body.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@app.put("/admin/locations/{location_id}", response_model=Location, tags=["Administration"])
def edit_location(location_id: int, body: LocationRequest, _: AdminIdentity, session: DbSession) -> Location:
    item = session.get(Location, location_id)
    if not item:
        raise HTTPException(status_code=404, detail="Location not found")
    for key, value in body.model_dump().items():
        setattr(item, key, value)
    session.commit()
    session.refresh(item)
    return item


@app.get("/admin/reports", response_model=list[InaccuracyReport], tags=["Administration"])
def admin_reports(_: AdminIdentity, session: DbSession) -> list[InaccuracyReport]:
    return list(session.exec(select(InaccuracyReport).order_by(InaccuracyReport.created_at.desc())).all())


@app.put("/admin/reports/{report_id}", response_model=InaccuracyReport, tags=["Administration"])
def update_report(report_id: int, body: StatusRequest, _: AdminIdentity, session: DbSession) -> InaccuracyReport:
    report = session.get(InaccuracyReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if body.status not in {"new", "reviewing", "resolved", "rejected"}:
        raise HTTPException(422, "Choose a valid report status")
    report.status = body.status
    session.commit()
    session.refresh(report)
    return report


@app.get("/admin/analytics/popular-searches", tags=["Administration"])
def popular_searches(_: AdminIdentity, session: DbSession) -> list[dict]:
    rows = session.exec(select(SearchLog.query, func.count(SearchLog.id)).group_by(SearchLog.query).order_by(func.count(SearchLog.id).desc(), SearchLog.query)).all()
    return [{"query": query, "count": count} for query, count in rows]


class AnnouncementRequest(BaseModel):
    title: str
    body: str
    location_id: int | None = None


@app.post("/admin/announcements", response_model=Announcement, status_code=201, tags=["Administration"])
def create_announcement(body: AnnouncementRequest, _: AdminIdentity, session: DbSession):
    if not body.title.strip() or not body.body.strip():
        raise HTTPException(422, "Title and message are required")
    if body.location_id is not None and not session.get(Location, body.location_id):
        raise HTTPException(404, "Location not found")
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
    if not body.title.strip() or not body.body.strip():
        raise HTTPException(422, "Title and message are required")
    if body.location_id is not None and not session.get(Location, body.location_id):
        raise HTTPException(404, "Location not found")
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
