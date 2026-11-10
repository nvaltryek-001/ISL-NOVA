"""ISL NOVA application factory.

    uvicorn app.main:app --host 0.0.0.0 --port 8000      (from backend/, PYTHONPATH=backend:ml)
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from .api import RateLimiter, build_routes, error_response, openapi
from .config import Settings
from .db import Database
from .migrate import migrate
from .routers import core, dataset, ml, personal, signs, translations
from .services import Jobs, LocalStorage, ModelService, ensure_user, seed_roles, seed_vocabulary

ROUTERS = [core.router, signs.router, translations.router, dataset.router, ml.router, personal.router]


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        d = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "level": record.levelname, "logger": record.name,
             "msg": record.getMessage()}
        for k in ("request_id", "method", "path", "status", "ms"):
            if hasattr(record, k):
                d[k] = getattr(record, k)
        if record.exc_info:
            d["exc"] = self.formatException(record.exc_info)
        return json.dumps(d)


def setup_logging() -> None:
    root = logging.getLogger("isl_nova")
    if not root.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(JsonFormatter())
        root.addHandler(h)
        root.setLevel(logging.INFO)
        root.propagate = False


class AppState:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db = Database(settings.database_url)
        self.storage = LocalStorage(settings.storage_dir)
        self.models = ModelService(settings.model_registry_dir, settings.allow_synthetic_model)
        self.jobs = Jobs()
        self.limiter = RateLimiter()

    def startup(self) -> None:
        log = logging.getLogger("isl_nova")
        applied = migrate(self.db)
        if applied:
            log.info("applied migrations %s", applied)
        with self.db.connect() as c:
            seed_roles(c)
            added = seed_vocabulary(c, self.settings.vocab_dir)
            if added:
                log.info("seeded %d vocabulary entries", added)
            s = self.settings
            if s.bootstrap_admin_email and s.bootstrap_admin_password:
                ensure_user(c, s.bootstrap_admin_email, s.bootstrap_admin_password, "Administrator", ["admin"],
                            s.pbkdf2_iterations)
        self.models.reload()
        with self.db.connect() as c:
            ml.sync_registry(self, c)
        log.info("model status: %s", "available" if self.models.predictor else self.models.error)


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(self), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net 'wasm-unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; "
        "connect-src 'self' https://cdn.jsdelivr.net https://storage.googleapis.com; worker-src 'self' blob:; "
        "frame-ancestors 'none'; base-uri 'self'"),
}


def create_app(settings: Settings | None = None) -> Starlette:
    setup_logging()
    settings = settings or Settings.from_env()
    state = AppState(settings)
    log = logging.getLogger("isl_nova.http")
    spec = openapi(ROUTERS)

    async def openapi_json(request: Request):
        return JSONResponse(spec)

    swagger = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14"
    docs_csp = ("default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data:; "
                "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'")

    async def docs(request: Request):
        return HTMLResponse(
            "<!doctype html><html lang='en'><head><title>ISL NOVA API</title><meta charset='utf-8'>"
            f"<link rel='stylesheet' href='{swagger}/swagger-ui.css'></head>"
            f"<body><div id='ui'></div><script src='{swagger}/swagger-ui-bundle.js'></script>"
            "<script src='/api/docs/init.js'></script></body></html>", headers={"Content-Security-Policy": docs_csp})

    async def docs_init(request: Request):
        return Response("SwaggerUIBundle({url:'/api/v1/openapi.json',dom_id:'#ui'});",
                        media_type="application/javascript")

    async def api_404(request: Request):
        return error_response(404, "not_found", "no such API route")

    routes = build_routes(state, ROUTERS)
    routes += [Route("/api/v1/openapi.json", openapi_json), Route("/api/docs", docs), Route("/api/docs/init.js", docs_init),
               Route("/api/{rest:path}", api_404, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])]

    dist = Path(settings.frontend_dist)
    if (dist / "index.html").exists():
        async def spa(request: Request):
            return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})

        if (dist / "assets").exists():
            routes.append(Mount("/assets", StaticFiles(directory=dist / "assets"), name="assets"))
        for static in ("favicon.svg", "manifest.webmanifest"):
            if (dist / static).exists():
                routes.append(Route(f"/{static}", lambda r, p=dist / static: FileResponse(p)))
        routes.append(Route("/{rest:path}", spa))

    @asynccontextmanager
    async def lifespan(app):
        state.startup()
        yield
        state.jobs.shutdown()

    class HeadersAndLogging(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            return await headers_and_logging(request, call_next)

    async def headers_and_logging(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        t0 = time.perf_counter()
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        if settings.env == "production":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        response.headers["X-Request-ID"] = rid
        if request.url.path.startswith("/api/"):
            log.info("request", extra={"request_id": rid, "method": request.method, "path": request.url.path,
                                       "status": response.status_code,
                                       "ms": round((time.perf_counter() - t0) * 1000, 1)})
        return response

    app = Starlette(routes=routes, lifespan=lifespan, middleware=[
        Middleware(HeadersAndLogging),
        Middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                   allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                   allow_headers=["Authorization", "Content-Type"], max_age=600)])
    app.state.isl = state
    return app


def __getattr__(name: str):  # lazy module-level app for `uvicorn app.main:app`
    if name == "app":
        a = create_app()
        globals()["app"] = a
        return a
    raise AttributeError(name)
