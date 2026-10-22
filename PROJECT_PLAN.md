# SDU Campus Assistant Web — implementation plan

This standalone web/API project was extracted from the existing campus assistant. See SOURCE.md for provenance; Flutter and all local user data stay in the original repository.

## Delivered application

- React, TypeScript, Vite, Tailwind and shadcn-style Radix components.
- FastAPI/SQLModel with PostgreSQL Compose tooling and lightweight SQLite development.
- Nine-digit ID/password authentication, revocable browser sessions, roles and public guest access.
- Original two-floor schematic maps and Dijkstra routes; stable IDs and explicit map uncertainty.
- Backend ranked search, contextual assistant, five-place favourites, saved accessibility preference, editable dated sample schedules, reports and updates.
- Protected administration for catalogue content, announcements, reports, roles and actual search analytics.
- Backend, component and real-browser tests using isolated test databases.

## Extraction and delivery

- [x] Copy tracked web/API/assets/tooling source without Flutter or local data.
- [x] Keep the original repository and currently running application unchanged.
- [x] Remove Flutter launch/test commands from this repository.
- [x] Document independent setup, ports, data and Docker volume boundaries.
- [x] Validate the extracted source and record results in docs/repository-extraction.md.
- [x] Create a clean initial local Git commit, without a remote or publication.

Current feature coverage and limitations are in docs/web-coverage.md. Neither schematic routes nor lift approaches are verified on site. Basement/full third-floor plans, real walking distances, live positioning and university-system integration remain unavailable.

## OpenRouter integration · 22 October 2026

- [x] Optional DeepSeek V4 Flash 0731 adapter using the existing httpx dependency.
- [x] Validated read-only campus search/location/next-class/updates/graph-route tools.
- [x] Owned, bounded conversation context and existing selectable clarification workflow.
- [x] Working assistant-to-map route handoff with server-generated segments.
- [x] Backend-only ignored configuration, bounded requests and visible rule-based fallback.
- [x] Automated offline-provider protocol tests, browser contract tests and live provider verification.

No changes to map geometry or university integration. No credentials are committed. Current verification evidence and operational limits are recorded in docs/openrouter-integration.md.
