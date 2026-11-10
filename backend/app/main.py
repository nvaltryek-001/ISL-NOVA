"""ISL NOVA application factory.

    uvicorn app.main:app --host 0.0.0.0 --port 8000      (from backend/, PYTHONPATH=backend:ml)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
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
from .metrics import METRICS
from .migrate import migrate
from .routers import analytics, classroom, core, dataset, ml, personal, practice, proposals, signs, translations
from .services import Jobs, ModelService, ensure_user, make_storage, seed_roles, seed_vocabulary

ROUTERS = [core.router, signs.router, translations.router, proposals.router, dataset.router, ml.router, practice.router, personal.router,
           classroom.router, analytics.router]


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
        self.storage = make_storage(settings)
        self.models = ModelService(settings.model_registry_dir, settings.allow_synthetic_model)
        if settings.redis_url:  # shared limiter + job queue for several API processes / workers
            from .redis_lite import Redis, RedisJobs, RedisRateLimiter
            r = Redis(settings.redis_url)
            self.limiter = RedisRateLimiter(r)
            self.jobs = RedisJobs(r)
        else:
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

    async def metrics(request: Request):
        tok = os.environ.get("METRICS_TOKEN", "")
        host = request.client.host if request.client else ""
        auth_ok = bool(tok) and request.headers.get("authorization", "") == f"Bearer {tok}"
        if not auth_ok and host not in ("127.0.0.1", "::1", "localhost", "testclient"):
            return error_response(403, "forbidden", "metrics are available from localhost or with METRICS_TOKEN")
        with state.db.connect() as c:
            signs = c.scalar("SELECT COUNT(*) FROM signs") or 0
            verified = c.scalar("SELECT COUNT(*) FROM signs WHERE verification_status = 'verified'") or 0
        return Response(METRICS.render({"isl_nova_model_available": int(state.models.predictor is not None),
                                        "isl_nova_vocabulary_signs": int(signs), "isl_nova_vocabulary_verified": int(verified)}),
                        media_type="text/plain; version=0.0.4")

    def _web_export():
        """The active model in the on-device format (LSTM, GRU, BiLSTM-attention), exported once per model."""
        pred = state.models.predictor
        if pred is None or pred.info.get("kind") not in ("lstm", "gru", "bilstm_attn"):
            return None
        out = settings.storage_dir / "web-export" / pred.info["model_id"]
        if not (out / "weights.bin").exists():
            from isl_nova_ml.export_web import export_web
            export_web(pred.dir, out)
        return out

    async def model_web(request: Request):
        out = _web_export()
        name = request.path_params["name"]
        if out is None or name not in ("model.json", "weights.bin"):
            return error_response(404, "not_found", "no on-device model for the active model")
        media = "application/json" if name == "model.json" else "application/octet-stream"
        return FileResponse(out / name, media_type=media, headers={"Cache-Control": "no-cache"})

    async def api_404(request: Request):
        return error_response(404, "not_found", "no such API route")

    routes = build_routes(state, ROUTERS)
    routes += [Route("/api/v1/openapi.json", openapi_json), Route("/api/docs", docs), Route("/metrics", metrics), Route("/api/docs/init.js", docs_init),
               Route("/model-web/{name}", model_web),
               Route("/api/{rest:path}", api_404, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])]

    dist = Path(settings.frontend_dist)
    if (dist / "index.html").exists():
        async def spa(request: Request):
            return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})

        if (dist / "assets").exists():
            routes.append(Mount("/assets", StaticFiles(directory=dist / "assets"), name="assets"))
        for static in ("favicon.svg", "manifest.webmanifest", "sw.js", "icon-512.png"):
            if (dist / static).exists():
                headers = {"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"} if static == "sw.js" else {}
                media = "application/manifest+json" if static.endswith(".webmanifest") else None
                routes.append(Route(f"/{static}", lambda r, p=dist / static, h=headers, m=media: FileResponse(p, headers=h, media_type=m)))
        routes.append(Route("/{rest:path}", spa))

    async def retention_loop():
        from .retention import run_retention
        while True:
            try:
                with state.db.connect() as c:
                    run_retention(c, settings, state.storage, apply=True)
            except Exception:  # noqa: BLE001 - never let the job take the server down
                logging.getLogger("isl_nova.retention").exception("retention run failed")
            await asyncio.sleep(settings.retention_interval_hours * 3600)

    @asynccontextmanager
    async def lifespan(app):
        state.startup()
        task = asyncio.create_task(retention_loop()) if settings.retention_interval_hours > 0 else None
        yield
        if task:
            task.cancel()
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
            METRICS.observe(request.method, request.url.path, response.status_code, time.perf_counter() - t0)
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
