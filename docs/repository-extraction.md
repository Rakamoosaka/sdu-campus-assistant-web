# Standalone repository verification

19 October 2026. Source snapshot: `64aef8a0e9339546e51ea6068b7bf143863b032f` in the original project. This repository has independent Git history. It initially had no remote; the later authorized private GitHub publication is recorded below.

## Contents and isolation

Copied tracked web/API/map/documentation files using an explicit allowlist. Forty-six copied code/assets/tooling files were verified byte-for-byte against the original; supplied frontend code, backend code, map JSON, SVG backgrounds, logo and source sketch remain unchanged. Documentation, Makefile and ignore rules were adapted for a standalone web repository. Flutter/native sources, original Git history, live databases/backups, actual environment files, installed dependencies and build output were not copied. Public presentation credentials remain documented sample configuration.

Ignore rules were checked for root/web/backend `.env` files, local databases, node_modules and dist. The two generated map catalogues remain identical. No source-project files or database records were modified. The original frontend returned HTTP 200 and API health returned ok after verification.

## Validation of the extracted source

Validation ran in a disposable copy under the system temporary directory. Web dependencies were installed from the committed lockfile with `npm ci --offline` using the existing package cache. Backend tests used the existing compatible Python environment, with fresh isolated test databases. Nothing was installed or built inside the clean deliverable folder.

| Check | Actual result |
|---|---|
| TypeScript and Vite production build | Passed |
| Backend pytest suite | 29 passed |
| Frontend component suite | 4 passed |
| Real Chromium E2E suite | 9 passed |
| Source/assets identity comparison | 46 files unchanged |
| Original application availability | API ok; frontend HTTP 200 |

The E2E suite used disposable servers on ports 8001/5174; the original application continued on 8000/5173. Existing build size/annotation and Python deprecation warnings remain as documented in web-coverage.md. PostgreSQL container execution and surveyed campus facts were not newly validated during extraction.

## Running this copy later

Follow the root README to create `.venv` and install backend/web dependencies. This repository starts with no personal data; its first run creates its own SQLite file and presentation accounts. Stop the old project from its own directory before starting this copy on the default ports. launchd job names are derived from each repository path, and Docker Compose uses a distinct default project name/volume. Neither repository's stop command is intended to stop the other.

The extraction itself did not publish anything. On 21 October 2026, the owner subsequently authorized the separate private GitHub repository https://github.com/Rakamoosaka/sdu-campus-assistant-web and its initial push. No application deployment or database transfer is included.
