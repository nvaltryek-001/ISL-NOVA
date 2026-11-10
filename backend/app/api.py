"""Minimal typed routing layer on Starlette + Pydantic.

Each route declares its body/query models, auth requirement, permission and
rate-limit bucket. The same declarations generate the OpenAPI document served
at /api/v1/openapi.json, so docs and validation cannot drift apart.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError
from pydantic.json_schema import models_json_schema
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from .db import Conn
from .security import ROLES, decode_token, has_perm

log = logging.getLogger("isl_nova.api")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: Any = None):
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details


def not_found(what: str) -> ApiError:
    return ApiError(404, "not_found", f"{what} not found")


def error_response(status: int, code: str, message: str, details: Any = None) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return JSONResponse(body, status_code=status)


class RateLimiter:
    """Sliding-window limiter (per process). Use a shared store for multi-instance deployments."""

    def __init__(self):
        self.hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str, limit: int, window: float = 60.0) -> bool:
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True


@dataclass
class Ctx:
    request: Request
    app: Any  # AppState
    db: Conn
    user: dict | None
    roles: set[str]
    body: Any = None
    query: Any = None
    params: dict = field(default_factory=dict)
    form: Any = None

    @property
    def ip(self) -> str:
        return self.request.client.host if self.request.client else "unknown"

    def require(self, perm: str) -> None:
        if not has_perm(self.roles, perm):
            raise ApiError(403, "forbidden", f"missing permission {perm}")

    def can(self, perm: str) -> bool:
        return has_perm(self.roles, perm)

    @property
    def uid(self) -> int:
        if not self.user:
            raise ApiError(401, "unauthenticated", "authentication required")
        return self.user["id"]


@dataclass
class RouteSpec:
    method: str
    path: str
    handler: Callable
    summary: str
    tag: str
    body: type[BaseModel] | None
    query: type[BaseModel] | None
    response: type[BaseModel] | None
    auth: str  # "required" | "optional" | "none"
    perm: str | None
    rate: str | None
    status: int
    multipart: bool


class Router:
    def __init__(self, tag: str):
        self.tag = tag
        self.specs: list[RouteSpec] = []

    def route(self, method: str, path: str, *, summary: str, body=None, query=None, response=None,
              auth: str = "required", perm: str | None = None, rate: str | None = "default",
              status: int = 200, multipart: bool = False):
        def deco(fn):
            self.specs.append(RouteSpec(method, path, fn, summary, self.tag, body, query, response, auth,
                                        perm, rate, status, multipart))
            return fn
        return deco

    def get(self, path, **kw):
        return self.route("GET", path, **kw)

    def post(self, path, **kw):
        return self.route("POST", path, **kw)

    def patch(self, path, **kw):
        return self.route("PATCH", path, **kw)

    def put(self, path, **kw):
        return self.route("PUT", path, **kw)

    def delete(self, path, **kw):
        return self.route("DELETE", path, **kw)


def _dump(v: Any) -> Any:
    if isinstance(v, BaseModel):
        return v.model_dump(mode="json")
    if isinstance(v, list):
        return [_dump(x) for x in v]
    if isinstance(v, dict):
        return {k: _dump(x) for k, x in v.items()}
    return v


def build_routes(state, routers: list[Router], prefix: str = "/api/v1") -> list[Route]:
    routes = []
    by_path: dict[str, list[RouteSpec]] = defaultdict(list)
    for r in routers:
        for s in r.specs:
            by_path[prefix + s.path].append(s)
    for path, specs in by_path.items():
        table = {s.method: s for s in specs}

        async def endpoint(request: Request, _table=table):
            spec = _table.get(request.method)
            if spec is None:
                return error_response(405, "method_not_allowed", "method not allowed")
            return await _dispatch(state, spec, request)

        routes.append(Route(path, endpoint, methods=list(table)))
    return routes


async def _dispatch(state, spec: RouteSpec, request: Request) -> Response:
    settings = state.settings
    ip = request.client.host if request.client else "unknown"
    if spec.rate:
        limit = settings.auth_rate_limit_per_minute if spec.rate == "auth" else settings.rate_limit_per_minute
        if not state.limiter.check(f"{spec.rate}:{ip}:{spec.path if spec.rate == 'auth' else ''}", limit):
            return error_response(429, "rate_limited", "too many requests, slow down")
    try:
        body = None
        form = None
        if spec.multipart:
            ctype = request.headers.get("content-type", "")
            if not ctype.startswith("multipart/form-data"):
                raise ApiError(415, "unsupported_media_type", "expected multipart/form-data")
            clen = int(request.headers.get("content-length") or 0)
            if clen > (settings.max_upload_mb + 1) * 1024 * 1024:
                raise ApiError(413, "too_large", f"upload exceeds {settings.max_upload_mb} MB")
            form = await request.form(max_files=1, max_fields=40)
        elif spec.body is not None:
            try:
                raw = await request.body()
                if len(raw) > 8 * 1024 * 1024:
                    raise ApiError(413, "too_large", "JSON body exceeds 8 MB")
                body = spec.body.model_validate_json(raw or b"{}")
            except ValidationError as exc:
                raise ApiError(422, "validation_error", "request body is invalid",
                               [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]) from exc
        query = None
        if spec.query is not None:
            try:
                query = spec.query.model_validate(dict(request.query_params))
            except ValidationError as exc:
                raise ApiError(422, "validation_error", "query parameters are invalid",
                               [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]) from exc

        def run():
            with state.db.connect() as conn:
                user, roles = _authenticate(state, conn, request)
                if spec.auth == "required" and user is None:
                    raise ApiError(401, "unauthenticated", "authentication required")
                ctx = Ctx(request, state, conn, user, roles, body, query, dict(request.path_params), form)
                if spec.perm:
                    ctx.require(spec.perm)
                return spec.handler(ctx)

        result = await run_in_threadpool(run)
        if form is not None:
            await form.close()
        if isinstance(result, Response):
            return result
        return JSONResponse(_dump(result), status_code=spec.status)
    except ApiError as exc:
        return error_response(exc.status, exc.code, exc.message, exc.details)
    except Exception:  # noqa: BLE001
        log.exception("unhandled error on %s %s", spec.method, spec.path)
        return error_response(500, "internal_error", "internal server error")


def _authenticate(state, conn: Conn, request: Request) -> tuple[dict | None, set[str]]:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None, set()
    decoded = decode_token(auth[7:].strip(), state.settings.jwt_secret)
    if decoded is None:
        raise ApiError(401, "invalid_token", "token is invalid or expired")
    uid, tv = decoded
    user = conn.one("SELECT id, email, display_name, is_active, preferred_language, settings, created_at, "
                    "token_version FROM users WHERE id = ?", (uid,))
    if user is None or not user["is_active"]:
        raise ApiError(401, "invalid_token", "account disabled or missing")
    if int(user["token_version"] or 0) != tv:
        raise ApiError(401, "invalid_token", "this session was signed out")
    user = {k: v for k, v in dict(user).items() if k != "token_version"}
    roles = {r["role_name"] for r in conn.all("SELECT role_name FROM user_roles WHERE user_id = ?", (uid,))}
    return user, roles


def openapi(routers: list[Router], prefix: str = "/api/v1") -> dict:
    models = []
    for r in routers:
        for s in r.specs:
            for m in (s.body, s.response):
                if m is not None and m not in models:
                    models.append(m)
    _, defs = models_json_schema([(m, "validation") for m in models], ref_template="#/components/schemas/{model}")
    paths: dict[str, dict] = defaultdict(dict)
    for r in routers:
        for s in r.specs:
            op: dict[str, Any] = {"summary": s.summary, "tags": [s.tag],
                                  "responses": {str(s.status): {"description": "OK"}}}
            if s.response is not None:
                op["responses"][str(s.status)]["content"] = {
                    "application/json": {"schema": {"$ref": f"#/components/schemas/{s.response.__name__}"}}}
            if s.body is not None:
                op["requestBody"] = {"required": True, "content": {
                    "application/json": {"schema": {"$ref": f"#/components/schemas/{s.body.__name__}"}}}}
            if s.multipart:
                op["requestBody"] = {"required": True, "content": {"multipart/form-data": {"schema": {"type": "object"}}}}
            if s.query is not None:
                op["parameters"] = [
                    {"name": n, "in": "query", "required": f.is_required(), "schema": {"type": "string"},
                     "description": f.description or ""}
                    for n, f in s.query.model_fields.items()]
            params = [p.strip("{}") for p in s.path.split("/") if p.startswith("{")]
            op.setdefault("parameters", [])
            op["parameters"] += [{"name": p, "in": "path", "required": True, "schema": {"type": "string"}} for p in params]
            if s.auth != "none":
                op["security"] = [{"bearer": []}] if s.auth == "required" else [{"bearer": []}, {}]
            if s.perm:
                op["description"] = f"Requires permission `{s.perm}`."
            paths[prefix + s.path][s.method.lower()] = op
    return {
        "openapi": "3.1.0",
        "info": {"title": "ISL NOVA API", "version": "0.1.0",
                 "description": "Indian Sign Language platform API. Roles: " + ", ".join(ROLES)},
        "paths": dict(paths),
        "components": {"schemas": defs.get("$defs", {}),
                       "securitySchemes": {"bearer": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}}},
    }
