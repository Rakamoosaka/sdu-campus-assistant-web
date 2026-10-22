# DeepSeek / OpenRouter integration · 22 October 2026

## Implemented

Optional backend adapter for `deepseek/deepseek-v4-flash-0731`. The public model catalogue was checked for exact ID and tools/tool_choice support. The existing httpx dependency calls OpenRouter directly; no extra AI SDK, vector database or external university integration was added.

Read-only model tools: `search_campus`, `get_location`, `get_next_class`, `get_campus_updates`, `plan_route`. Identity and preferences come from the server, never model arguments. `present_answer` validates IDs against records actually observed during the current request. Every turn first requires a fresh tool read. A separate scoped context retains candidate choices; the original server-validated selection flow remains usable. Planned routes use actual Dijkstra output and open the route with its original start, destination and per-floor segments.

The UI shows whether a reply came from DeepSeek or the campus fallback. New chat resets the active conversation. A configured-status badge is not a provider health claim; per-answer source/fallback labels report the actual engine used. Provider errors are reduced to safe reason codes rather than returned verbatim.

## Local configuration and data

The supplied key is stored only in the ignored root `.env` with owner-only permissions. It is neither a VITE variable nor a repository file; the frontend service unsets backend credentials before starting. `.env.example` contains only a blank placeholder. Compose passes backend variables explicitly. API status returns only configured/model/engine, never credentials.

The running local app was switched from the original project to this standalone repository on the same ports 5173/8000. Its local configuration references the existing SQLite file, preserving accounts, sessions, favourites and preferences without copying them into Git. A database backup was made before the additive assistantconversation table was created. The original source repository remains unchanged. Future teammates use their own ignored configuration and database by default.

Questions and relevant tool results are sent to OpenRouter and the model provider. Relevant personal questions can send the current account’s stored profile (name, SDU ID, email, role and faculty), saved places, route preference, sample timetable and reports through owner-scoped tools. Passwords and session tokens are never included. User-typed text remains part of the question. Signed-in next-class access is account-scoped; guests cannot request another owner's timetable.

## Limits and fallback

- Five provider requests maximum per turn; up to three concurrent turns per API process.
- Default 45-second total deadline; configurable within 2–90 seconds.
- Default rate limits: ten AI turns/account/minute, thirty/IP/minute, ninety/process/minute. These in-memory limits are not a distributed quota.
- Last six exchanges retained, with a 12-hour conversation expiry. Clarification candidates expire after 30 minutes. Periodic pruning is not scheduled.
- No automatic paid retries; timeout, busy/rate limits, invalid key, exhausted credits, provider errors, malformed responses or unverified action IDs use the working rule-based fallback.
- Search logs are queued until the remote call ends, so the API does not hold a SQLite writer while waiting on a model.

Grounding constrains data access and validates executable actions. Natural-language wording is still model-generated and is not a guarantee of factual perfection; hours, contacts, positions and route accessibility should be checked against the returned catalogue/details. Unknown facts remain unconfirmed. Schematic map limits and sample timetable labelling are unchanged.

## Verification

Automated tests do not use the real key or make paid provider calls. Backend tests patch the provider boundary/HTTP transport while exercising actual catalogue, preference, route, identity and persistence logic. The E2E test server explicitly disables the provider key.

| Check | Result |
|---|---|
| Backend pytest | 47 passed |
| Frontend components | 4 passed |
| Browser E2E | 11 passed |
| TypeScript / Vite production build | Passed |
| Live exact-model printing recommendation | OpenRouter engine; Print & Stationery from the catalogue; unconfirmed hours/contact |
| Live follow-up about closing time | OpenRouter engine; fresh location lookup; hours remain unconfirmed |
| Live Main Entrance → D201 route | OpenRouter engine; schematic_draft; nine actual drawable segments and floor transfer |
| Live next-class paraphrase | OpenRouter engine; current student’s actual stored sample lesson, Almaty time and D201 map action |
| Manual running-browser check | Live printing question and follow-up show DeepSeek source and clickable campus location |

The browser suite includes nine existing real-backend workflows plus two UI contract tests: conversation-ID propagation/new-chat reset and assistant-to-map handoff using an actual server-generated route. Those two replace model replies at the browser boundary; they do not claim to exercise the live provider. The separate live checks above verify actual model requests.

Existing build size/annotation and Python deprecation warnings remain. PostgreSQL container execution was not verified in this batch; the local run and automated fixtures use SQLite.
