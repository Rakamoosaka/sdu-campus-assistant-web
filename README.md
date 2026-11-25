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

Stop with `make web-stop`. On macOS, the launcher submits current-login launchd jobs so servers survive the end of a Codex command/chat turn; it does not install boot/login startup items. The stop command removes those jobs. Logs, errors and recorded service PIDs live in ignored `.local-run/`. If you instead start `make backend-local` and `make web-dev` in separate terminals, stop each with Ctrl-C. `make web-build` checks TypeScript and produces `web/dist/`. The launcher builds the app and serves it with Vite preview. Both Vite modes proxy `/api` requests to FastAPI with same-origin browser cookies. Use `make web-dev` for hot reload. For hosting, the root Dockerfile serves the site and API from one address; see Deploy (Render + Neon) below.

## Deploy (Render + Neon, free)

The root `Dockerfile` builds the website and serves it together with the API (under `/api`) from one FastAPI process (`backend/app/server.py`). On Render's free plan the container keeps no files, so the data lives in a free [Neon](https://neon.com) Postgres database. `render.yaml` describes the service.

1. **Database (Neon):** sign up at neon.com and create a project (region: Frankfurt / `eu-central-1`). On the project dashboard, click **Connect** and copy the connection string (`postgresql://…?sslmode=require`).
2. **App (Render):** sign in at render.com with GitHub. Choose **New → Blueprint**, pick this repository, and paste the Neon connection string into `DATABASE_URL` when asked. Render generates `JWT_SECRET` itself.
3. Wait for the first deploy, then open the `https://sdu-campus-assistant.onrender.com` address shown on the service (Render may add a suffix if the name is taken). The demo logins work after the first start, which creates the tables and demo data.
4. Optional: in the service's **Environment** tab, add `OPENROUTER_API_KEY` (and `OPENROUTER_MODEL`) for the AI assistant; without them the built-in assistant answers.

Notes:
- The free service falls asleep after about 15 idle minutes and takes up to a minute to wake. Open the link a minute before presenting.
- Data stays in Neon across sleeps, restarts and redeploys. Each push to `main` redeploys.
- `COOKIE_SECURE=true` is set in the image. No `CORS_ORIGINS` is needed because the site and API share one address. Without `JWT_SECRET`, the server uses a random secret, so everyone is signed out after each restart.
- `postgres://` and `postgresql://` addresses are accepted as-is.

To try the same image locally: `docker build -t sdu-campus .` then `docker run -p 8000:8000 -v sdu-data:/data sdu-campus` and open http://127.0.0.1:8000. Add `-e DATABASE_URL=postgresql://…` to use Postgres instead of the SQLite file on the volume.

## PostgreSQL and Docker

```bash
docker compose up --build -d
npm --prefix web run dev
```

Compose preserves `sdu_postgres_data`; **do not use `down -v`** to stop a demonstration. `docker compose down` retains data. Stop the standalone local API first to free port 8000. The API container uses PostgreSQL directly. Schema setup is additive (`create_all` for missing tables, plus newer columns added to existing tables on startup); no existing tables or columns are dropped. See [database-schema.md](database-schema.md) for the update procedure.

pgAdmin remains at [http://127.0.0.1:5050](http://127.0.0.1:5050), login `admin@sdu.edu.kz` / `admin`. Register host `database`, port `5432`, database/user `sdu_campus` / `sdu`, password `sdu_demo_password`. These are local presentation credentials. The full backend test suite also passes on PostgreSQL 17 (see Tests).

## What works

Timetable and Announcements are switched off in the interface for now (`web/src/features.ts`). Their pages, admin tools, server endpoints and data are kept; set a flag to `true` to bring a section back.


- Empty ID/password login and registration forms, visibility controls, server-enforced roles and guest entry. New registrations are Students.
- Real HttpOnly browser sessions, CSRF checks, restricted CORS, server-side logout and session restoration.
- Supplied anniversary identity; desktop navigation, mobile sheet, zoom/pan, explicit zoom/fit and floor buttons.
- Search with exact room ranking, normalized spacing, aliases and typo tolerance; searches are logged in the database.
- Stable mapped locations, details, five persisted saved places per account, reports on incorrect location details or blocked corridors, stairs and lifts (picked from the planned route or around the selected place), tracked by the reporter on the My reports page with an unread badge (guests included; guest reports move to the account on sign-in). Admins fix a reported place and resolve the report in one step, see duplicates grouped, and can close paths until a set time. There is no separate profile page: the account menu (your name in the sidebar) holds the Avoid stairs switch and Log out / Sign in. Share links open the selected destination directly, including for visitors without an account.
- The built app supports downloading public floor plans and the place catalogue for offline browsing and search. Offline mode requires HTTPS or localhost and a completed download in that browser. Routing and the assistant require the API.
- Existing Dijkstra graph, floor-specific route segments, route framing, ordered transfers and avoid-stairs preference saved per account or guest session and applied by the server, a step-free map layer, admin-recorded step-free access per place, and explanations when no suitable route exists. Administrators can close a reported path or mark it not step-free, and routes avoid it immediately.
- Grounded rule-based assistant: service recommendations, next-class lookup, selectable ambiguity resolution and map actions.
- Editable sample student/teacher schedules, UTC storage and explicit Asia/Almaty display/selection of the next upcoming lesson. New accounts start with empty schedules and can add lessons.
- Public announcements with an optional show-from/until window (Asia/Almaty), listed on the Announcements page and in the linked place's details; admins create, edit, schedule and delete them. Protected admin edits of location details (name, block, floor label, hours, contact, search aliases, step-free access), report status review, role management and actual SQL search aggregates.

The coverage checklist and verified test results are in [docs/web-coverage.md](docs/web-coverage.md).

## Map facts and limits

Floors 1 and 2 are schematic. Floor 2 follows the supplied red sketch and includes its connected corridors, Bochka platforms and library branch over a muted footprint. S1 stays removed. S3/S4/S5/S8 and known connections are retained. S6 connects 1 directly to 3 and skips 2; separate canteen stairs connect 2 to 3. Floor 3 has only a canteen terminal, with no invented general corridors or basement layout. D/F/H lifts route only through explicitly connected floor-1/2 landing nodes; their other served floors do not create routes automatically.

Original D101–D104 records are retained. Other four-room D–H patterns on floors 1/2 and door connections are assumed/schematic. Library internal infrastructure and other unknown positions remain unpositioned. Places, categories, map positions and route connections come only from the campus map file; administrators edit details, not the map. All routes remain unverified, and metres/walking times stay unavailable. Excluding stairs can honestly leave no route to the canteen.

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

The E2E runner starts isolated servers on ports 8001/5174 and never uses the user's database. Backend fixtures create a fresh database per test. To run the backend tests on PostgreSQL, point `TEST_DATABASE_URL` at a throwaway database (its `public` schema is wiped before every test), for example `TEST_DATABASE_URL=postgresql+psycopg://sdu:pw@127.0.0.1:55432/sdu_campus make test-api`. Flutter sources and Flutter-only commands are intentionally excluded.

## Optional map regeneration

The map is traced from the posted evacuation plans for floors 1–3 (`docs/map-source/evacuation-plans/`). Install the dependencies with `.venv/bin/pip install -r scripts/requirements-map.txt`, then run `cd scripts && ../.venv/bin/python import_campus_map.py ../docs/map-source`. See [Map integration](docs/map-integration.md) for the sources and the decisions behind them.

## Repository and data separation

This is a clean local repository extracted from the verified web migration. Its source and scope are recorded in [SOURCE.md](SOURCE.md). It has its own Git history and a private GitHub remote: [Rakamoosaka/sdu-campus-assistant-web](https://github.com/Rakamoosaka/sdu-campus-assistant-web). The original project, running services and databases are unchanged. Local databases, accounts, secrets, dependency folders and build output were not copied.

Install dependencies using the commands above. The first local startup creates a separate SQLite database with presentation seed accounts; personal accounts/saves from the original database are not transferred. No university authentication or timetable integration is implied. Docker Compose uses this repository's distinct default project name and therefore a separate named database volume; avoid overriding it to the original project's name.

This is the main campus app checkout. It combines the AI assistant, current mapped routes, destination sharing, staircase icons and offline maps. Run it on ports 5173/8000 with `make web-start` here. The earlier Project Management checkout is retained as historical source and should stay stopped.

- [Implementation plan](PROJECT_PLAN.md)
- [Web design system](design-system.md)
- [Database, sessions and migration](database-schema.md)
- [Map integration](docs/map-integration.md)

## Optional DeepSeek AI through OpenRouter

The assistant uses `deepseek/deepseek-v4-flash-0731` when the backend has `OPENROUTER_API_KEY` configured in the ignored root `.env`. Add your own key there; do not put it in `web/.env`, a `VITE_` variable or source control. The `.env.example` contains a blank key and the chosen model ID. `make web-start` loads the configuration; restart with `make web-stop && make web-start` after changing it. Docker Compose forwards the same settings to the API container.

The model calls validated, read-only tools for catalogue search, location details, the current account's next sample lesson, announcements currently showing and graph routes. It interprets paraphrases/follow-ups, while the backend resolves identity, applies saved accessibility preferences and validates every returned action ID. Chat choices remain clickable. Route responses open their actual per-floor segments in the map instead of inventing navigation instructions. Campus records and approaches remain schematic/unconfirmed where documented.

`OPENROUTER_TIMEOUT_SECONDS` defaults to 45. Each turn allows at most six provider requests, including the scope assessment, with three concurrent AI turns per API process; in-memory rate limits default to 10 turns/account/minute, 30/IP/minute and 90/process/minute. This is a local course-project limit, not a distributed deployment quota. API outages, missing credit, invalid keys, timeouts, limits or invalid model actions produce the existing rule-based answer with a visible fallback label. No key means the basic assistant is used directly. There are no automatic paid retries.

Conversation context is stored locally for up to 12 hours, scoped to the signed-in account/guest session and limited to the last six exchanges. **New chat** resets the UI's context. Questions and relevant tool results are sent to OpenRouter and its selected model provider. Relevant personal questions can send the signed-in account’s stored name, email, SDU ID, role, faculty, saved places, preferences, sample timetable and reports through account-scoped tools. Passwords and session tokens are never included; user-typed text is part of the question. No university data integration is added.

`make test` and `make test-e2e` do not make paid AI calls. AI protocol tests stub the external provider while exercising real campus tools; browser tests cover the chat contract and real route handoff. Live-provider checks are recorded separately in [docs/openrouter-integration.md](docs/openrouter-integration.md).

The assistant first classifies requests into supported campus intents, redirects unrelated tasks and asks for clarification when the reference is unclear. Tool access is limited to the assessed intent. Displayed answers are assembled by the backend from verified tool results, so model-authored prose cannot become the final answer. Existing conversation ownership checks, read-only tools and account isolation still apply. If AI is unavailable, the fallback accepts explicit campus questions and exact room/service names.
