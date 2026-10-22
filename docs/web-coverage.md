# Web replacement coverage · updated 22 October 2026

Status is based on real API/database behavior and browser execution. There is no public deployment. Optional OpenRouter AI is now supported; the app still works without a key.

## Completed

- [x] React/TypeScript/Vite, Tailwind v4, local shadcn-style Button/Dialog primitives, Router, TanStack Query/Axios, React Hook Form/Zod authentication.
- [x] Actual anniversary logo, navy/blue/gold identity, desktop map workspace, compact rail, narrow-screen sheet/bottom navigation and visible name/role/initials.
- [x] Empty login/registration inputs, nine ASCII-digit ID validation, password visibility, confirmation validation, guest entry and discreet demo access.
- [x] Persisted PBKDF2 hashes; existing demo roles no longer reset; new registration cannot self-assign Admin.
- [x] HttpOnly/SameSite browser sessions, optional Secure cookies, CSRF headers, configured cross-origin CORS plus same-origin Swagger access, database revocation/logout. Current roles/active status are checked server-side.
- [x] Public guest map/search/routes/updates/assistant. API rejects guest saves, preferences, schedules, reports/history and admin operations.
- [x] Reuse of both SVGs, 103 mapped catalogue entries and graph, with unchanged stable IDs. Current database detail fields overlay map metadata.
- [x] Dynamic rooms/markers rendered once; correct room/floor focus from search/saved/schedule/assistant actions; unpositioned records remain unpinned.
- [x] Buttons for zoom in/out/fit/floors alongside pan/pinch, route framing, floor-specific segments, approximate terminal styling, clear route, numbered directions and floor-transfer controls.
- [x] Existing Dijkstra, normal stairs/lift choices, profile-only avoid-stairs persistence and server-side application of the saved preference. Floor-3 canteen stairs-excluded routes fail honestly.
- [x] Map facts retained: S1 absent; S3/S4/S5/S6/S8; S6 skips 2; separate 2→3 canteen stairs; D/F/H mapped lift approaches; floor-2 sketch branches/platforms and muted context; no fabricated basement/full third floor.
- [x] Exact-code ranking, case/space normalization, editable aliases/service synonyms, typo tolerance (`libary`), no-results state and actual search logging.
- [x] Assistant recommendations from current catalogue data (medical/printing/study/food), room questions, hours/contact grounding, actual competing choices with expiring owned context and working map actions.
- [x] Dated, editable, persisted sample student/teacher schedules; UTC normalization; next upcoming instant using Asia/Almaty; empty and unmapped handling. New users start empty and can add sample lessons.
- [x] Five distinct saved places enforced in API/UI; idempotent duplicate save; remove/replace; user isolation; historical saves over five remain visible rather than being truncated.
- [x] Reports retain selected location; real admin location/hour/contact updates and catalogue additions; create/edit announcements; report status changes; repeated role updates and current-role enforcement.
- [x] Admin counts use actual records; popular searches use SQL GROUP BY/COUNT and return empty when no events exist.
- [x] Additive table setup, local database backups, recoverable Git checkpoint, unchanged Flutter/map source assets, `.env.example` files, launch/stop commands and lockfile.

## Verification

| Check | Result |
|---|---|
| `PYTHONPATH=backend .venv/bin/pytest backend/tests -q` | 47 tests passed, including AI grounding, scoped conversations, provider failure modes and concurrent saves |
| `npm --prefix web test` | 4 component tests passed |
| `npm --prefix web run test:e2e` | 11 Chromium browser tests passed against disposable servers/database; external AI disabled |
| `npm --prefix web run build` | TypeScript check and production build passed |
| npm dependency audit | 0 reported vulnerabilities after updates |
| Manual browser check | Guest entry, D201 search/floor-2 switch and cross-floor route verified in the running narrow-screen app |
| Preservation comparison | Map assets, backend compiled map, importers and Flutter files unchanged from checkpoint `83ffd00`; no original database rows removed. Five legacy demo location rows updated by the existing map importer, with their originals retained in the backup |

Browser cases cover login identity/avatar/reload/logout; guest no-save; D201 floor/route; preference → lift; five saves/removal/replacement/reload; persisted admin edit visible in details; mobile controls/no horizontal overflow; assistant recommendation/clarification selection; dated timetable create/edit/reload/map action. Component tests check empty/invalid forms, password confirmation/visibility, real error presentation and retry callbacks. Backend fixtures create a temporary database per test; no test requires records from earlier runs. Browser test databases are removed with their test server process.

## Partial / unverified

- PostgreSQL/Compose configuration and per-user row locking are retained. The Docker daemon was unavailable, so this batch executed SQLite only; PostgreSQL execution/concurrent-worker stress testing is not claimed.
- Legacy JWTs without session IDs remain bearer-only until expiry and lack retroactive revocation. New browser and mobile tokens have revocable session IDs. See the database documentation for the compatibility boundary.
- Keyboard controls and contrast/readability were improved, but a full assistive-technology/WCAG audit and cross-browser/device matrix have not been run. Touch-scale room geometry may require zooming.
- The build emits a large-chunk advisory (~640kB JavaScript before gzip, ~204kB gzip) and upstream Zod annotation warnings; they do not prevent a successful build. Python dependencies emit existing deprecation warnings.
- Existing time-only `campusclass` records stay preserved; dated web schedules use the additive `samplelesson` table. Expired session/context pruning is not scheduled.
- Adding/editing a location's catalogue details is supported. Creating new surveyed geometry, changing corridor topology or inventing route attachments through the admin UI is intentionally outside this migration; source/importer edits are required.

## Unavailable pending campus facts / outside scope

- Surveyed distances/walking times, live indoor GPS, certified step-free approaches and live lift availability.
- Basement/full floor-3 plans, missing door/landing positions, unconfirmed parking, missing service hours/contacts and unknown library internal positions.
- University SSO, real university timetable synchronization and public deployment. Sample data is labelled and editable locally.

## Optional AI follow-up

DeepSeek V4 Flash 0731 through OpenRouter is implemented and live-verified. See [openrouter-integration.md](openrouter-integration.md) for the read-only tools, privacy boundary, fallbacks, limits and exact distinction between deterministic automated tests and live checks. Keys are local-only and never committed.
