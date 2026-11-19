import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.auth import Forbidden, Unauthenticated, get_lang
from app.config import ROOT_DIR, get_settings
from app.db import init_db
from app.deps import business_error_handler, error_response, forbidden_handler, unauthenticated_handler, validation_handler
from app.i18n import t
from app.routers import auth, clients, core, measurements, norm_rules, parameters, pools
from app.utils import BusinessError

BUILD_HINT = "The web UI is not built yet. Run: cd frontend && npm install && npm run build"


@asynccontextmanager
async def lifespan(_application: FastAPI):
    init_db()
    yield


def _mount_spa(application: FastAPI, dist: Path) -> None:
    """Serve the built SPA: hashed files under /assets, index.html for every other GET."""
    index_file = dist / "index.html"
    log = logging.getLogger("uvicorn.error")  # uvicorn's default config prints this logger ("INFO: ...")
    if index_file.is_file():
        log.info("Serving the web UI from %s", dist.resolve())
    else:
        log.warning("Web UI not built: %s is missing (API only). %s", index_file, BUILD_HINT)
    if (dist / "assets").is_dir():
        application.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")

    @application.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    def unknown_api(rest: str, request: Request) -> JSONResponse:
        return error_response(404, t(get_lang(request), "err.unknown_endpoint"), key="err.unknown_endpoint")

    @application.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if not index_file.is_file():  # checked per request: a build made while running is picked up
            return error_response(503, f"{BUILD_HINT} (this server looks for {index_file})")
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index_file)


def create_app(frontend_dist: Optional[Path] = None) -> FastAPI:
    settings = get_settings()
    try:
        ZoneInfo(settings.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise RuntimeError(f"TIMEZONE={settings.timezone!r} is not an IANA time zone (e.g. America/Mexico_City)") from None
    if settings.secret_key == "YOUR_SECRET_KEY_HERE":
        logging.getLogger(__name__).warning("SECRET_KEY is the placeholder value; set a real one in .env.")

    application = FastAPI(title=settings.app_name, lifespan=lifespan)
    application.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="aquacontrol_session",
        same_site="lax",
        https_only=settings.session_https_only,
    )
    application.add_exception_handler(BusinessError, business_error_handler)
    application.add_exception_handler(Forbidden, forbidden_handler)
    application.add_exception_handler(Unauthenticated, unauthenticated_handler)
    application.add_exception_handler(RequestValidationError, validation_handler)
    for module in (core, auth, clients, pools, parameters, norm_rules, measurements):
        application.include_router(module.router)

    default_dist = Path(settings.frontend_dist) if settings.frontend_dist else ROOT_DIR / "frontend" / "dist"
    _mount_spa(application, frontend_dist or default_dist)
    return application


app = create_app()
