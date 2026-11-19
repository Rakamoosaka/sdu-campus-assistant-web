"""Production entry point: the built website and the API on one address, with the API under /api."""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from . import main

WEB_DIST = Path(os.getenv("WEB_DIST", Path(__file__).resolve().parents[2] / "web" / "dist")).resolve()

site = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@site.on_event("startup")
def startup() -> None:
    # Mounted apps do not run their own startup hooks.
    main.seed_database()


site.mount("/api", main.app)


@site.get("/{path:path}", include_in_schema=False)
def web_page(path: str) -> FileResponse:
    file = (WEB_DIST / path).resolve()
    if path and file.is_file() and file.is_relative_to(WEB_DIST):
        cache = "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-cache"
        return FileResponse(file, headers={"Cache-Control": cache})
    # Every other address is a page of the single-page app (/map, /reports, ...).
    return FileResponse(WEB_DIST / "index.html", headers={"Cache-Control": "no-cache"})
