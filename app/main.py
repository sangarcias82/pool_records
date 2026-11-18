import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.auth import Forbidden
from app.config import ROOT_DIR, get_settings
from app.db import init_db
from app.deps import business_error_handler, error_response, forbidden_handler, validation_handler
from app.routers import auth, clients, core, pools
from app.utils import BusinessError

BUILD_HINT = "The web UI is not built yet. Run: cd frontend && npm install && npm run build"


@asynccontextmanager
async def lifespan(_application: FastAPI):
    init_db()
    yield


def _mount_spa(application: FastAPI, dist: Path) -> None:
    """Serve the built SPA: hashed files under /assets, index.html for every other GET."""
    index_file = dist / "index.html"
    if (dist / "assets").is_dir():
        application.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")

    @application.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    def unknown_api(rest: str) -> JSONResponse:
        return error_response(404, "Unknown API endpoint")

    @application.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if not index_file.is_file():
            return error_response(503, BUILD_HINT)
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index_file)


def create_app(frontend_dist: Optional[Path] = None) -> FastAPI:
    settings = get_settings()
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
    application.add_exception_handler(RequestValidationError, validation_handler)
    for module in (core, auth, clients, pools):
        application.include_router(module.router)

    default_dist = Path(settings.frontend_dist) if settings.frontend_dist else ROOT_DIR / "frontend" / "dist"
    _mount_spa(application, frontend_dist or default_dist)
    return application


app = create_app()
