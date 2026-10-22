> Standalone web repository: The latest web schema/session behavior is documented in section 10. Earlier Flutter references describe the source project. See [SOURCE.md](SOURCE.md) for extraction history.

# SDU Campus Assistant Database Schema

**Version:** 1.0
**Database:** PostgreSQL 17 for the full demonstration; SQLite for lightweight local development
**Data layer:** SQLModel + SQLAlchemy
**API:** FastAPI

## 1. Purpose

The database supports role-based authentication, guest sessions, campus locations, routes, saved places, accessibility preferences, schedules, announcements, information reports, and search analytics.

The running schema is created from the SQLModel classes in `backend/app/main.py`. PostgreSQL data is persisted in the Docker volume `sdu_postgres_data`.

## 2. High-level data domains

| Domain | Tables |
|---|---|
| Identity and access | `user`, `authaccount`, `guestsession`, `roleoverride` |
| Personalisation | `preference`, `favorite` |
| Campus navigation | `location`, `route`, `routestep` |
| Academic information | `campusclass` |
| Campus communication | `announcement`, `inaccuracyreport` |
| Analytics | `searchlog` |

## 3. Entity-relationship diagram

The following diagram shows the logical relationships used by the application service layer.

![SDU Campus Assistant database entity-relationship diagram](docs/database-erd.svg)

Presentation exports are available as [`docs/database-erd.svg`](docs/database-erd.svg) and [`docs/database-erd.png`](docs/database-erd.png). The SVG is recommended for slides because it remains sharp at any size.

```mermaid
erDiagram
    user ||--|| authaccount : authenticates_with
    user ||--o| preference : configures
    user ||--o{ favorite : saves
    location ||--o{ favorite : is_saved_as
    location ||--o{ route : starts_route
    location ||--o{ route : ends_route
    route ||--o{ routestep : contains
    user ||--o{ campusclass : owns_schedule
    location ||--o{ campusclass : hosts
    location ||--o{ announcement : relates_to
    location ||--o{ inaccuracyreport : is_reported_in
    location ||--o{ searchlog : is_selected_in

    user {
        int id PK
        string full_name
        string email UK
        string role
        string faculty
        boolean active
        datetime created_at
    }

    authaccount {
        int id PK
        string sdu_id UK
        string password_hash
        int user_id FK,UK
        datetime created_at
    }

    guestsession {
        int id PK
        string session_key UK
        datetime created_at
    }

    roleoverride {
        int id PK
        string email UK
        string role
        string reason
    }

    preference {
        int id PK
        int user_id FK
        boolean accessible_routes
    }

    location {
        int id PK
        string name
        string category
        string block
        string floor
        float x
        float y
        string opening_hours
        string contact
        boolean accessible
        string aliases
    }

    route {
        int id PK
        int start_location_id FK
        int destination_location_id FK
        int distance_m
        int duration_min
        boolean accessible
    }

    routestep {
        int id PK
        int route_id FK
        int step_order
        string instruction
    }

    favorite {
        int id PK
        int user_id FK
        int location_id FK
    }

    campusclass {
        int id PK
        string owner_email FK
        string course
        string room
        string starts_at
        int location_id FK
        string kind
    }

    announcement {
        int id PK
        string title
        string body
        datetime published_at
        int location_id FK
    }

    inaccuracyreport {
        int id PK
        string author
        int location_id FK
        string message
        string status
        datetime created_at
    }

    searchlog {
        int id PK
        string actor
        string query
        int selected_location_id FK
        datetime created_at
    }
```

## 4. Table dictionary

### `user`

Stores the application profile and assigned role for every registered person.

| Column | Type | Rules | Purpose |
|---|---|---|---|
| `id` | Integer | Primary key | Internal user identifier |
| `full_name` | String | Required | Display name |
| `email` | String | Required, unique, indexed | Internal SDU identity key derived as `{sdu_id}@sdu.edu.kz` |
| `role` | String | Required, indexed | `student`, `teacher`, or `admin` |
| `faculty` | String | Required; default `SDU` | Organisational information |
| `active` | Boolean | Required; default `true` | Enables account suspension |
| `created_at` | Date/time | Required | Account creation audit timestamp |

The mobile interface uses only the nine-digit SDU ID. The internal email-shaped key is retained for compatibility with seeded schedule and role data.

### `authaccount`

Separates login credentials from the public user profile.

| Column | Type | Rules | Purpose |
|---|---|---|---|
| `id` | Integer | Primary key | Credential record identifier |
| `sdu_id` | String | Required, unique, indexed | Nine-digit login ID |
| `password_hash` | String | Required | Salted PBKDF2-SHA256 password representation |
| `user_id` | Integer | Required, unique, indexed; logical FK → `user.id` | One-to-one profile link |
| `created_at` | Date/time | Required | Credential creation timestamp |

Passwords are never stored as plain text. Each hash uses a random 16-byte salt and 600,000 PBKDF2 iterations.

### `guestsession`

Stores anonymous sessions created by **Continue as Guest**.

| Column | Type | Rules | Purpose |
|---|---|---|---|
| `id` | Integer | Primary key | Guest record identifier |
| `session_key` | String | Required, unique, indexed | Random UUID used as the token subject |
| `created_at` | Date/time | Required | Session creation timestamp |

Guest sessions do not own favourites, saved preferences, schedules, or reports.

### `roleoverride`

Assigns demonstration roles that cannot yet be inferred from the numeric ID.

| Column | Type | Rules | Purpose |
|---|---|---|---|
| `id` | Integer | Primary key | Override identifier |
| `email` | String | Required, unique, indexed | Internal SDU identity key |
| `role` | String | Required | Assigned teacher/admin role |
| `reason` | String | Required | Audit explanation |

New accounts default to Student unless an override exists.

### `preference`

Stores registered-user navigation preferences.

| Column | Type | Rules | Purpose |
|---|---|---|---|
| `id` | Integer | Primary key | Preference identifier |
| `user_id` | Integer | Required, indexed; logical FK → `user.id` | Preference owner |
| `accessible_routes` | Boolean | Required; default `false` | Prefer step-free routes and elevators |

### `location`

The central campus entity used by map pins, search, routes, schedules, and announcements.

| Column | Type | Rules | Purpose |
|---|---|---|---|
| `id` | Integer | Primary key | Location identifier |
| `name` | String | Required, indexed | Human-readable name or room code |
| `category` | String | Required, indexed | Classroom, Food, Study, Office, etc. |
| `block` | String | Required, indexed | Campus block A–H |
| `floor` | String | Required | Floor description |
| `x`, `y` | Float | Required | Normalised map coordinates from 0.0 to 1.0 |
| `opening_hours` | String | Required | Display-ready opening hours |
| `contact` | String | Required | Phone or service contact |
| `accessible` | Boolean | Required | Entrance/elevator accessibility flag |
| `aliases` | String | Required | Comma-separated alternate search terms |

Normalised coordinates allow the same location records to be drawn responsively over the campus-map image.

### `route`

Stores a route option between two campus locations.

| Column | Type | Rules | Purpose |
|---|---|---|---|
| `id` | Integer | Primary key | Route identifier |
| `start_location_id` | Integer | Required; logical FK → `location.id` | Route origin |
| `destination_location_id` | Integer | Required; logical FK → `location.id` | Route destination |
| `distance_m` | Integer | Required | Walking distance in metres |
| `duration_min` | Integer | Required | Estimated walking time |
| `accessible` | Boolean | Required; default `false` | Step-free route indicator |

### `routestep`

Stores ordered instructions for a route.

| Column | Type | Rules | Purpose |
|---|---|---|---|
| `id` | Integer | Primary key | Step identifier |
| `route_id` | Integer | Required, indexed; logical FK → `route.id` | Parent route |
| `step_order` | Integer | Required | Display order |
| `instruction` | String | Required | Human-readable instruction |

### `favorite`

Join table for registered users and saved campus locations.

| Column | Type | Rules | Purpose |
|---|---|---|---|
| `id` | Integer | Primary key | Saved-place identifier |
| `user_id` | Integer | Required, indexed; logical FK → `user.id` | Owner |
| `location_id` | Integer | Required, indexed; logical FK → `location.id` | Saved destination |

Guests cannot create favourite records. Tapping a saved place in Flutter opens that location on the map and exposes the Route action.

### `campusclass`

Stores seeded student timetables and teacher schedules.

| Column | Type | Rules | Purpose |
|---|---|---|---|
| `id` | Integer | Primary key | Class identifier |
| `owner_email` | String | Required, indexed; logical link → `user.email` | Schedule owner |
| `course` | String | Required | Course name |
| `room` | String | Required | Room code |
| `starts_at` | String | Required | Display-ready class time |
| `location_id` | Integer | Required; logical FK → `location.id` | Map destination |
| `kind` | String | Required | `student` or `teacher` schedule entry |

### `announcement`

Stores public campus news and location-linked events.

| Column | Type | Rules | Purpose |
|---|---|---|---|
| `id` | Integer | Primary key | Announcement identifier |
| `title` | String | Required | Headline |
| `body` | String | Required | Announcement content |
| `published_at` | Date/time | Required | Publication timestamp |
| `location_id` | Integer | Nullable; logical FK → `location.id` | Optional map destination |

### `inaccuracyreport`

Tracks registered-user reports for outdated campus information.

| Column | Type | Rules | Purpose |
|---|---|---|---|
| `id` | Integer | Primary key | Report identifier |
| `author` | String | Required | User identity recorded with the report |
| `location_id` | Integer | Nullable; logical FK → `location.id` | Reported location |
| `message` | String | Required | Requested correction |
| `status` | String | Required, indexed; default `new` | Review workflow state |
| `created_at` | Date/time | Required | Submission timestamp |

### `searchlog`

Provides aggregate search analytics without changing location records.

| Column | Type | Rules | Purpose |
|---|---|---|---|
| `id` | Integer | Primary key | Search event identifier |
| `actor` | String | Required | User/session label |
| `query` | String | Required, indexed | Search phrase |
| `selected_location_id` | Integer | Nullable; logical FK → `location.id` | Chosen result, when recorded |
| `created_at` | Date/time | Required | Search timestamp |

## 5. Authentication and authorisation flow

1. Registration validates a nine-digit SDU ID and a password of at least eight characters.
2. The backend creates a `user` profile and an `authaccount` password record.
3. Teacher and administrator demonstration IDs are resolved through `roleoverride`; other new IDs default to Student.
4. Login verifies the PBKDF2 password hash.
5. FastAPI issues a 12-hour HS256 JWT containing the SDU ID and role.
6. Protected endpoints resolve the token identity and enforce registered-user, teacher, or administrator access.
7. Guest access creates a `guestsession` and a JWT with the `guest` role.

## 6. Implemented indexes and uniqueness

The physical schema currently includes:

- Unique indexed `user.email`
- Unique indexed `authaccount.sdu_id`
- Unique indexed `authaccount.user_id`
- Unique indexed `guestsession.session_key`
- Unique indexed `roleoverride.email`
- Indexes on roles, names, categories, blocks, queries, report status, and relationship lookup fields

Relationships marked as **logical FK** are currently resolved by the FastAPI service layer. A production migration should add explicit PostgreSQL foreign-key constraints, cascade rules, and compound uniqueness such as `favorite(user_id, location_id)`.

## 7. Seeded demonstration data

The startup seed creates:

- Five students: Yerassyl, Daulet, Omar, Aitore, and Aidyn
- One teacher and one administrator
- Login credentials for each seeded account
- Twelve searchable campus locations
- Three location-linked announcements
- A Project Management class/schedule record for the demonstration accounts
- Teacher and administrator role overrides

The shared course-demo password is documented in `README.md`; the database stores only its salted hash.

## 8. Teacher demonstration in pgAdmin

Start the stack:

```bash
docker compose up --build -d
```

Open `http://127.0.0.1:5050` and register the PostgreSQL server:

| Setting | Value |
|---|---|
| Host | `database` |
| Port | `5432` |
| Database | `sdu_campus` |
| Username | `sdu` |
| Password | `sdu_demo_password` |

### Show users and roles

```sql
SELECT a.sdu_id, u.full_name, u.role, u.active, u.created_at
FROM authaccount AS a
JOIN "user" AS u ON u.id = a.user_id
ORDER BY u.role, u.full_name;
```

### Show saved places

```sql
SELECT u.full_name, l.name AS saved_location, l.block, l.floor
FROM favorite AS f
JOIN "user" AS u ON u.id = f.user_id
JOIN location AS l ON l.id = f.location_id
ORDER BY u.full_name, l.name;
```

### Show accessibility preferences

```sql
SELECT u.full_name, p.accessible_routes
FROM preference AS p
JOIN "user" AS u ON u.id = p.user_id;
```

### Show popular searches

```sql
SELECT query, COUNT(*) AS search_count
FROM searchlog
GROUP BY query
ORDER BY search_count DESC, query;
```

### Show information-report workflow

```sql
SELECT r.id, r.author, l.name AS location, r.message, r.status, r.created_at
FROM inaccuracyreport AS r
LEFT JOIN location AS l ON l.id = r.location_id
ORDER BY r.created_at DESC;
```

## 9. Source of truth

| Concern | Source |
|---|---|
| SQLModel table definitions | `backend/app/main.py` |
| PostgreSQL service configuration | `docker-compose.yml` |
| API request/response documentation | `http://127.0.0.1:8000/docs` |
| Product and role scope | `PROJECT_PLAN.md` |

## 10. Web migration (19 October 2026) — current behavior

This section supersedes the mobile-only authentication and timetable descriptions above.

### Safe additive update

Startup uses SQLModel `metadata.create_all`, adding **only missing tables**. It does not rename/drop tables, modify existing columns, truncate favourites or reset hashes/roles. There are no Alembic revisions in this project; do not run an invented `alembic upgrade` migration. Back up before starting a new version. This batch saved original local `.db` files under `.local-backups/` using SQLite's online backup API. For PostgreSQL, use `docker compose exec -T database pg_dump -U sdu sdu_campus > /path/to/backup.sql` before an upgrade. Keep the existing named volume. Future incompatible column changes need an explicit migration.

The existing first-time map importer retains stable IDs but replaces old demo location fields with compiled map records when `[campus-map-v1]` is absent. Once that marker exists, later starts preserve admin edits. Old unconfirmed records remain physically stored but retired IDs are excluded from public directory/search. The pre-import SQLite snapshot preserves original demo field values.

### Added tables

| Table | Columns / responsibility |
|---|---|
| `browsersession` | Random `id` PK, `subject`, `csrf`, UTC `expires_at`, `revoked`; server-side revocation for browser cookies and newly issued bearer tokens |
| `assistantcontext` | Opaque `id` PK, `actor`, `choices_json`, `route_intent`, UTC `expires_at`; actual candidate IDs and ownership for 30-minute clarification selections |
| `samplelesson` | `id` PK, `user_id`, `course`, UTC `starts_at`, nullable `location_id`, `room`, `kind`, `sample`; editable dated sample schedules |
| `datamigration` | `key` PK; records the one-time dated sample seed without rewriting historical data |

`campusclass` retains all original time-only records. They are not treated as dated upcoming lessons. New `/students/me/timetable` and `/teachers/me/schedule` responses use `samplelesson`. Dated seed lessons are added once for presentation accounts for the following seven days, attached to existing D201/F102/H203 IDs. After those dates pass, no upcoming lessons is the correct response. New users start empty; authenticated users can add/edit their own lessons. Sample rows remain explicitly labelled sample data. Offset-aware inputs are required; a SQLAlchemy type converts values to UTC before storage on both SQLite and PostgreSQL. The next lesson uses actual instants and Asia/Almaty for display. Missing mapped room links remain nullable.

### Sessions and permissions

Login/register/guest responses retain `access_token` for Flutter compatibility and also set `sdu_session`: HttpOnly, SameSite=Lax, 12-hour lifetime, Secure when `COOKIE_SECURE=true`. The React app never saves the JWT in localStorage. Axios sends cookies; `/auth/csrf` returns the session token for the `X-CSRF-Token` header on mutations. Non-configured browser origins are rejected, including login origins. Same-origin Vite `/api` proxying is the default. Use HTTPS, a random `JWT_SECRET` and Secure cookies for any future shared host.

Logout revokes the server session and clears its cookie; replay of either that cookie or its JWT is rejected. Existing legacy Flutter JWTs without a session ID remain accepted **only through Authorization Bearer**, until their original 12-hour expiry. They cannot become browser cookies and do not gain retroactive logout revocation. All tokens resolve current account status and role from the database, so a role change applies immediately. Browser sessions/context rows expire logically; periodic pruning of expired rows is not yet scheduled.

Registration always creates a Student account; callers cannot supply an Admin role. Startup creates missing demo accounts but no longer overwrites roles for existing profiles. Admin role edits update an existing role override instead of violating the email uniqueness constraint.

Guest personal endpoints (favourites, preferences, reports/history and schedules) reject with 403. Admin writes remain protected in the API. Report location IDs are validated and retained. Lesson editing checks ownership. Favourite insertion serializes on the user row in PostgreSQL, checks distinct saved locations, allows duplicates idempotently and rejects a sixth location. Historical saves over five remain visible until the owner removes them. SQLite reserves its writer with BEGIN IMMEDIATE before the count; a concurrent-save regression verifies that a sixth distinct save is rejected. PostgreSQL multiworker stress testing remains unverified.

### Analytics and content

`searchlog` now records actual frontend searches. Ranking uses normalized names/codes, editable aliases, service synonyms and bounded fuzzy matching. SQL GROUP BY/COUNT supplies `/admin/analytics/popular-searches`; an empty log returns an empty list without fallback counts. Location requests default hours/contact to `Not confirmed`. No campus contacts or hours are invented. Announcement create/edit endpoints persist the title/body and optional location. Inaccuracy status accepts only new/reviewing/resolved/rejected.

## 11. OpenRouter assistant (22 October 2026)

`assistantconversation` is an additive SQLModel table: opaque string `id` PK, indexed `actor`, bounded `messages_json`, UTC `expires_at`. It retains the last 12 user/assistant messages (six exchanges), with a 12-hour lifetime. Access checks resolve the current actor before reading a supplied conversation ID. Missing/other-owner IDs return 404; expired IDs return 410. Clarification candidate IDs still use `assistantcontext` with a 30-minute expiry. Old conversations are not automatically pruned yet.

The model has no SQL or write-tool access. Search/location/next-lesson/update/route callbacks use the current Session and server-resolved identity. Next-class calls accept no owner identifier. Route calls use the saved preference. Final map actions must reference location IDs returned by tools in that request. Every turn forces a fresh read before offering the final-response tool, including follow-ups with history. AI searches create real SearchLog records with actor `assistant`. Client responses never contain the API key or raw provider errors.

All existing accounts, favourites, preferences, map IDs and historical schedules remain unchanged. The current local service has been switched to the standalone web repository; its ignored environment configuration references the pre-existing local SQLite file to retain sessions/data, with a pre-AI backup under `.local-backups/`. This local path/key configuration is not distributed in Git.
