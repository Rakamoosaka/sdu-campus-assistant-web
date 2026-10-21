# SDU Campus Assistant

A responsive, map-first React web app backed by FastAPI, SQLModel and PostgreSQL (or SQLite locally). This is a project-management course semester project, with no official university integration. This standalone repository contains the web app, API and map tooling. The Flutter frontend remains in the original project and is not included here.

## Run locally

Requirements: Python 3.13+ and Node 22.12+ (Node 24 used for verification). From this repository:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
npm ci --prefix web
cp .env.example .env
make web-start
```

If `.venv` and the dependencies already exist, use `make web-start` directly. Keep existing `.env` settings rather than overwriting them. The launch script reads root `.env`; Vite also reads `web/.env` when present.

- Web app: [http://127.0.0.1:5173](http://127.0.0.1:5173)
- API/Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

Stop with `make web-stop`. On macOS, the launcher submits current-login launchd jobs so servers survive the end of a Codex command/chat turn; it does not install boot/login startup items. The stop command removes those jobs. Logs, errors and recorded service PIDs live in ignored `.local-run/`. If you instead start `make backend-local` and `make web-dev` in separate terminals, stop each with Ctrl-C. `make web-build` checks TypeScript and produces `web/dist/`. Vite's development proxy makes `/api` requests to FastAPI with same-origin browser cookies. A future production host needs an equivalent `/api` reverse proxy and SPA history fallback; `vite preview` alone does not provide an API proxy. No public hosting is configured.

## PostgreSQL and Docker

```bash
docker compose up --build -d
npm --prefix web run dev
```

Compose preserves `sdu_postgres_data`; **do not use `down -v`** to stop a demonstration. `docker compose down` retains data. Stop the standalone local API first to free port 8000. The API container uses PostgreSQL directly. Schema setup is additive (`create_all` for missing tables); no existing tables or columns are dropped. See [database-schema.md](database-schema.md) for the update procedure.

pgAdmin remains at [http://127.0.0.1:5050](http://127.0.0.1:5050), login `admin@sdu.edu.kz` / `admin`. Register host `database`, port `5432`, database/user `sdu_campus` / `sdu`, password `sdu_demo_password`. These are local presentation credentials. Docker's daemon was stopped in the verification environment, so the delivered run uses SQLite; PostgreSQL container execution is unverified in this batch.

## What works

- Empty ID/password login and registration forms, visibility controls, server-enforced roles and guest entry. New registrations are Students.
- Real HttpOnly browser sessions, CSRF checks, restricted CORS, server-side logout and session restoration.
- Supplied anniversary identity; desktop navigation, mobile sheet, zoom/pan, explicit zoom/fit and floor buttons.
- Search with exact room ranking, normalized spacing, aliases and typo tolerance; searches are logged in the database.
- Stable mapped locations, details, five persisted saved places per account, reports tied to selected locations.
- Existing Dijkstra graph, floor-specific route segments, route framing, ordered transfers and saved avoid-stairs preference (Profile only).
- Grounded rule-based assistant: service recommendations, next-class lookup, selectable ambiguity resolution and map actions.
- Editable sample student/teacher schedules, UTC storage and explicit Asia/Almaty display/selection of the next upcoming lesson. New accounts start with empty schedules and can add lessons.
- Public dated updates; protected admin location/hour/contact edits, add-location forms, announcement creation/editing, report status review, role management and actual SQL search aggregates.

The coverage checklist and verified test results are in [docs/web-coverage.md](docs/web-coverage.md).

## Map facts and limits

Floors 1 and 2 are schematic. Floor 2 follows the supplied red sketch and includes its connected corridors, Bochka platforms and library branch over a muted footprint. S1 stays removed. S3/S4/S5/S8 and known connections are retained. S6 connects 1 directly to 3 and skips 2; separate canteen stairs connect 2 to 3. Floor 3 has only a canteen terminal, with no invented general corridors or basement layout. D/F/H lifts route only through explicitly connected floor-1/2 landing nodes; their other served floors do not create routes automatically.

Original D101–D104 records are retained. Other four-room D–H patterns on floors 1/2 and door connections are assumed/schematic. Library internal infrastructure and other unknown positions remain unpositioned. Admin-added catalogue entries do not automatically gain surveyed coordinates or graph connections. All routes remain unverified, and metres/walking times stay unavailable. Excluding stairs can honestly leave no route to the canteen.

## Demo access

The sign-in screen has a discreet **Demo access** link. Presentation IDs: Student `240103049`, Teacher `240000001`, Administrator `240000002`; password `Campus123!`. Existing hashes and role assignments are retained on startup. Do not use presentation passwords/secrets in a shared deployment.

## Tests

```bash
make test                 # isolated backend tests + frontend component tests
cd web
npx playwright install chromium
cd ..
make test-e2e             # real API + browser; disposable temporary SQLite database
```

The E2E runner starts isolated servers on ports 8001/5174 and never uses the user's database. Backend fixtures create a fresh database per test. Flutter sources and Flutter-only commands are intentionally excluded.

## Optional map regeneration

Install the importer dependency with `.venv/bin/pip install -r scripts/requirements-map.txt`, then run `.venv/bin/python scripts/import_campus_map.py docs/map-source`. Supplied geometry and uncertainty remain the source of truth.

## Repository and data separation

This is a clean local repository extracted from the verified web migration. Its source and scope are recorded in [SOURCE.md](SOURCE.md). It has its own Git history and a private GitHub remote: [Rakamoosaka/sdu-campus-assistant-web](https://github.com/Rakamoosaka/sdu-campus-assistant-web). The original project, running services and databases are unchanged. Local databases, accounts, secrets, dependency folders and build output were not copied.

Install dependencies using the commands above. The first local startup creates a separate SQLite database with presentation seed accounts; personal accounts/saves from the original database are not transferred. No university authentication or timetable integration is implied. Docker Compose uses this repository's distinct default project name and therefore a separate named database volume; avoid overriding it to the original project's name.

Both repositories use ports 5173/8000 by default. If the original app is running there, stop it before running this copy on those ports. Stop the original with `make web-stop` **from the original directory**, then run `make web-start` here. Keep databases separate unless you deliberately perform a backed-up data migration. No data migration or remote publication is part of this extraction.

- [Implementation plan](PROJECT_PLAN.md)
- [Web design system](design-system.md)
- [Database, sessions and migration](database-schema.md)
- [Map integration](docs/map-integration.md)
- [Floor-2 source and graph details](docs/floor-2-integration.md)
