"""Health, authentication, profile, notifications and administration."""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field, field_validator

from .. import totp
from ..api import ApiError, Ctx, Router, not_found
from ..db import jdump, jload, utcnow
from ..security import DUMMY_HASH, MIN_PASSWORD, ROLES, create_token, hash_password, verify_password
from ..services import audit

router = Router("core")
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")


class RegisterIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=MIN_PASSWORD, max_length=200)
    display_name: str = Field(min_length=1, max_length=120)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("invalid email address")
        return v


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)
    otp: str | None = Field(default=None, max_length=12)


class OtpIn(BaseModel):
    code: str = Field(min_length=6, max_length=12)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 - OAuth token type, not a secret
    expires_in: int
    user: dict


class ProfileIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    preferred_language: str | None = Field(default=None, pattern="^(en|hi|kn)$")
    settings: dict | None = None
    current_password: str | None = None
    new_password: str | None = Field(default=None, min_length=MIN_PASSWORD, max_length=200)


class UserAdminIn(BaseModel):
    roles: list[str] | None = None
    is_active: bool | None = None


class UsersQuery(BaseModel):
    q: str | None = None


class AuditQuery(BaseModel):
    action: str | None = None
    limit: int = Field(default=100, ge=1, le=500)


def user_out(ctx_or_conn, user: dict, roles: set[str] | None = None) -> dict:
    conn = ctx_or_conn.db if isinstance(ctx_or_conn, Ctx) else ctx_or_conn
    if roles is None:
        roles = {r["role_name"] for r in conn.all("SELECT role_name FROM user_roles WHERE user_id = ?", (user["id"],))}
    return {"id": user["id"], "email": user["email"], "display_name": user["display_name"],
            "preferred_language": user.get("preferred_language", "en"), "is_active": bool(user.get("is_active", True)),
            "settings": jload(user.get("settings")) or {}, "roles": sorted(roles), "created_at": user.get("created_at"),
            "two_factor": bool(user.get("totp_enabled"))}


@router.get("/health", summary="Service health", auth="none", rate=None)
def health(ctx: Ctx):
    from isl_nova_ml.contract import CONTRACT_NAME

    from ..migrate import status

    st = status(ctx.app.db)
    ms = ctx.app.models
    return {"status": "ok" if not st["pending"] else "degraded", "database": ctx.app.db.dialect,
            "migrations": {"applied": len(st["applied"]), "pending": st["pending"]},
            "model": {"available": ms.predictor is not None, "reason": ms.error},
            "feature_contract": CONTRACT_NAME,
            "landmark_extractor": {"server_side_available": bool(ctx.app.settings.hand_model_path)},
            "time": utcnow(), "version": "0.1.0"}


@router.post("/auth/register", summary="Create an account (learner role)", auth="none", body=RegisterIn,
             response=TokenOut, rate="auth", status=201)
def register(ctx: Ctx):
    if not ctx.app.settings.allow_open_registration:
        raise ApiError(403, "registration_closed", "self-registration is disabled")
    b: RegisterIn = ctx.body
    if ctx.db.one("SELECT id FROM users WHERE email = ?", (b.email,)):
        raise ApiError(409, "email_taken", "an account with this email already exists")
    with ctx.db.transaction():
        uid = ctx.db.insert("users", {"email": b.email, "display_name": b.display_name.strip(),
                                      "password_hash": hash_password(b.password, ctx.app.settings.pbkdf2_iterations),
                                      "created_at": utcnow()})
        ctx.db.insert("user_roles", {"user_id": uid, "role_name": "learner", "granted_at": utcnow()}, pk=None)
        audit(ctx.db, uid, "auth.register", f"user:{uid}", ip=ctx.ip)
    user = ctx.db.one("SELECT * FROM users WHERE id = ?", (uid,))
    tok, exp = create_token(uid, ctx.app.settings.jwt_secret, ctx.app.settings.jwt_ttl_minutes)
    return {"access_token": tok, "token_type": "bearer", "expires_in": exp, "user": user_out(ctx, user)}


@router.post("/auth/login", summary="Exchange credentials for an access token", auth="none", body=LoginIn,
             response=TokenOut, rate="auth")
def login(ctx: Ctx):
    b: LoginIn = ctx.body
    user = ctx.db.one("SELECT * FROM users WHERE email = ?", (b.email.strip().lower(),))
    ok = verify_password(b.password, user["password_hash"] if user else DUMMY_HASH)
    if not user or not ok or not user["is_active"]:
        audit(ctx.db, user["id"] if user else None, "auth.login_failed", None, None, ctx.ip)
        raise ApiError(401, "invalid_credentials", "email or password is incorrect")
    if user.get("totp_enabled"):
        if not b.otp:
            raise ApiError(401, "otp_required", "enter the 6-digit code from your authenticator app")
        step = totp.verify(user["totp_secret"], b.otp)
        if step is None or (user.get("totp_last_step") is not None and step <= int(user["totp_last_step"])):
            audit(ctx.db, user["id"], "auth.otp_failed", f"user:{user['id']}", ip=ctx.ip)
            raise ApiError(401, "invalid_otp", "the authenticator code is wrong or was already used")
        ctx.db.update("users", {"totp_last_step": step}, "id = ?", (user["id"],))
    ctx.db.update("users", {"last_login_at": utcnow()}, "id = ?", (user["id"],))
    audit(ctx.db, user["id"], "auth.login", f"user:{user['id']}", ip=ctx.ip)
    tok, exp = create_token(user["id"], ctx.app.settings.jwt_secret, ctx.app.settings.jwt_ttl_minutes,
                            int(user["token_version"] or 0))
    return {"access_token": tok, "token_type": "bearer", "expires_in": exp, "user": user_out(ctx, user)}


@router.post("/auth/logout-all", summary="Sign out everywhere: revoke every token issued to this account",
             status=200)
def logout_all(ctx: Ctx):
    with ctx.db.transaction():
        ctx.db.execute("UPDATE users SET token_version = COALESCE(token_version, 0) + 1 WHERE id = ?", (ctx.uid,))
        audit(ctx.db, ctx.uid, "auth.logout_all", f"user:{ctx.uid}", ip=ctx.ip)
    return {"ok": True}


@router.post("/me/2fa/setup", summary="Start two-factor setup: a new TOTP secret (not active until confirmed)")
def totp_setup(ctx: Ctx):
    row = ctx.db.one("SELECT totp_enabled FROM users WHERE id = ?", (ctx.uid,))
    if row["totp_enabled"]:
        raise ApiError(409, "two_factor_enabled", "two-factor sign-in is already on; turn it off first")
    secret = totp.new_secret()
    ctx.db.update("users", {"totp_secret": secret}, "id = ?", (ctx.uid,))
    return {"secret": secret, "otpauth_uri": totp.otpauth_uri(secret, ctx.user["email"])}


@router.post("/me/2fa/enable", summary="Confirm a code from the authenticator app and turn two-factor on", body=OtpIn)
def totp_enable(ctx: Ctx):
    row = ctx.db.one("SELECT totp_secret, totp_enabled FROM users WHERE id = ?", (ctx.uid,))
    if row["totp_enabled"] or not row["totp_secret"]:
        raise ApiError(409, "two_factor_state", "start setup first")
    step = totp.verify(row["totp_secret"], ctx.body.code)
    if step is None:
        raise ApiError(400, "invalid_otp", "the code does not match; check the time on your phone")
    with ctx.db.transaction():
        ctx.db.update("users", {"totp_enabled": True, "totp_last_step": step}, "id = ?", (ctx.uid,))
        audit(ctx.db, ctx.uid, "auth.2fa_enabled", f"user:{ctx.uid}", ip=ctx.ip)
    return {"two_factor": True}


@router.post("/me/2fa/disable", summary="Turn two-factor off (needs a current code)", body=OtpIn)
def totp_disable(ctx: Ctx):
    row = ctx.db.one("SELECT totp_secret, totp_enabled FROM users WHERE id = ?", (ctx.uid,))
    if not row["totp_enabled"]:
        raise ApiError(409, "two_factor_state", "two-factor sign-in is not on")
    if totp.verify(row["totp_secret"], ctx.body.code) is None:
        raise ApiError(400, "invalid_otp", "the code does not match")
    with ctx.db.transaction():
        ctx.db.update("users", {"totp_enabled": False, "totp_secret": None, "totp_last_step": None},
                      "id = ?", (ctx.uid,))
        audit(ctx.db, ctx.uid, "auth.2fa_disabled", f"user:{ctx.uid}", ip=ctx.ip)
    return {"two_factor": False}


@router.get("/me", summary="Current user profile")
def me(ctx: Ctx):
    return user_out(ctx, ctx.user, ctx.roles)


@router.patch("/me", summary="Update profile, preferences or password", body=ProfileIn)
def update_me(ctx: Ctx):
    b: ProfileIn = ctx.body
    vals: dict = {}
    if b.display_name is not None:
        vals["display_name"] = b.display_name.strip()
    if b.preferred_language is not None:
        vals["preferred_language"] = b.preferred_language
    if b.settings is not None:
        allowed = {"high_contrast", "reduced_motion", "large_text", "speech_rate", "kiosk_language", "camera_id",
                   "daily_goal"}
        vals["settings"] = jdump({k: v for k, v in b.settings.items() if k in allowed})
    if b.new_password:
        row = ctx.db.one("SELECT password_hash FROM users WHERE id = ?", (ctx.uid,))
        if not b.current_password or not verify_password(b.current_password, row["password_hash"]):
            raise ApiError(400, "bad_password", "current password is incorrect")
        vals["password_hash"] = hash_password(b.new_password, ctx.app.settings.pbkdf2_iterations)
    ctx.db.update("users", vals, "id = ?", (ctx.uid,))
    if "password_hash" in vals:
        audit(ctx.db, ctx.uid, "auth.password_changed", f"user:{ctx.uid}", ip=ctx.ip)
    return user_out(ctx, ctx.db.one("SELECT * FROM users WHERE id = ?", (ctx.uid,)))


@router.get("/notifications", summary="My notifications")
def notifications(ctx: Ctx):
    return ctx.db.all("SELECT id, title, body, read_at, created_at FROM notifications WHERE user_id = ? "
                      "ORDER BY id DESC LIMIT 50", (ctx.uid,))


@router.post("/notifications/{nid}/read", summary="Mark a notification read")
def read_notification(ctx: Ctx):
    n = ctx.db.update("notifications", {"read_at": utcnow()}, "id = ? AND user_id = ?", (int(ctx.params["nid"]), ctx.uid))
    if not n:
        raise not_found("notification")
    return {"ok": True}


@router.get("/admin/users", summary="List users", perm="admin:users", query=UsersQuery)
def list_users(ctx: Ctx):
    q = ctx.query.q
    rows = ctx.db.all("SELECT * FROM users" + (" WHERE email LIKE ? OR display_name LIKE ?" if q else "") +
                      " ORDER BY id LIMIT 500", (f"%{q}%", f"%{q}%") if q else ())
    return [user_out(ctx, u) for u in rows]


@router.patch("/admin/users/{uid}", summary="Change roles or deactivate a user", perm="admin:users", body=UserAdminIn)
def admin_update_user(ctx: Ctx):
    uid = int(ctx.params["uid"])
    user = ctx.db.one("SELECT * FROM users WHERE id = ?", (uid,))
    if not user:
        raise not_found("user")
    b: UserAdminIn = ctx.body
    with ctx.db.transaction():
        if b.roles is not None:
            bad = set(b.roles) - set(ROLES)
            if bad:
                raise ApiError(422, "validation_error", f"unknown roles {sorted(bad)}")
            if uid == ctx.uid and "admin" not in b.roles:
                raise ApiError(400, "self_demotion", "you cannot remove your own admin role")
            ctx.db.execute("DELETE FROM user_roles WHERE user_id = ?", (uid,))
            for r in sorted(set(b.roles)):
                ctx.db.insert("user_roles", {"user_id": uid, "role_name": r, "granted_by": ctx.uid,
                                             "granted_at": utcnow()}, pk=None)
        if b.is_active is not None:
            if uid == ctx.uid and not b.is_active:
                raise ApiError(400, "self_deactivation", "you cannot deactivate yourself")
            ctx.db.update("users", {"is_active": b.is_active}, "id = ?", (uid,))
        audit(ctx.db, ctx.uid, "admin.user_updated", f"user:{uid}", b.model_dump(exclude_none=True), ctx.ip)
    return user_out(ctx, ctx.db.one("SELECT * FROM users WHERE id = ?", (uid,)))


RESET_MINUTES = 30


def _reset_hash(code: str) -> str:
    return hashlib.sha256(code.strip().encode()).hexdigest()


@router.post("/admin/users/{uid}/password-reset", summary="Issue a one-time password reset code (30 min)",
             perm="admin:users", status=201)
def admin_issue_reset(ctx: Ctx):
    uid = int(ctx.params["uid"])
    if not ctx.db.one("SELECT id FROM users WHERE id = ?", (uid,)):
        raise not_found("user")
    code = secrets.token_urlsafe(24)
    expires = (datetime.now(UTC) + timedelta(minutes=RESET_MINUTES)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with ctx.db.transaction():
        # a new code replaces any unused earlier one
        ctx.db.execute("DELETE FROM password_resets WHERE user_id = ? AND used_at IS NULL", (uid,))
        ctx.db.insert("password_resets", {"user_id": uid, "token_hash": _reset_hash(code), "issued_by": ctx.uid,
                                          "expires_at": expires, "created_at": utcnow()})
        audit(ctx.db, ctx.uid, "admin.password_reset_issued", f"user:{uid}", ip=ctx.ip)
    # the code is shown once; hand it to the user through a trusted channel
    return {"code": code, "expires_at": expires}


class ResetIn(BaseModel):
    code: str = Field(min_length=10, max_length=200)
    new_password: str = Field(min_length=MIN_PASSWORD, max_length=200)


@router.post("/auth/reset-password", summary="Set a new password with a one-time reset code", auth="none",
             body=ResetIn, rate="auth")
def reset_password(ctx: Ctx):
    b: ResetIn = ctx.body
    row = ctx.db.one("SELECT * FROM password_resets WHERE token_hash = ?", (_reset_hash(b.code),))
    if not row or row["used_at"] or str(row["expires_at"]) < utcnow():
        audit(ctx.db, None, "auth.password_reset_failed", None, None, ctx.ip)
        raise ApiError(400, "invalid_reset_code", "the reset code is invalid, used or expired")
    with ctx.db.transaction():
        ctx.db.update("password_resets", {"used_at": utcnow()}, "id = ?", (row["id"],))
        # new password + sign out everywhere; an admin-issued reset is also the recovery path
        # for a lost authenticator, so two-factor is turned off and must be set up again
        ctx.db.execute("UPDATE users SET password_hash = ?, token_version = COALESCE(token_version, 0) + 1, "
                       "totp_enabled = ?, totp_secret = NULL, totp_last_step = NULL WHERE id = ?", (hash_password(b.new_password, ctx.app.settings.pbkdf2_iterations),
                                        False, row["user_id"]))
        audit(ctx.db, row["user_id"], "auth.password_reset", f"user:{row['user_id']}", ip=ctx.ip)
    return {"ok": True}


class RetentionIn(BaseModel):
    apply: bool = False


@router.post("/admin/retention", summary="Run the data-retention job (dry run unless apply=true)",
             perm="admin:users", body=RetentionIn)
def admin_retention(ctx: Ctx):
    from ..retention import run_retention
    out = run_retention(ctx.db, ctx.app.settings, ctx.app.storage, apply=ctx.body.apply)
    if ctx.body.apply:
        audit(ctx.db, ctx.uid, "admin.retention_run", None, out.get("deleted"), ctx.ip)
    return out


@router.get("/admin/audit", summary="Audit log", perm="admin:audit", query=AuditQuery)
def audit_log(ctx: Ctx):
    q = ctx.query
    sql = ("SELECT a.id, a.action, a.target, a.detail, a.ip, a.created_at, u.email AS actor "
           "FROM audit_logs a LEFT JOIN users u ON u.id = a.actor_id")
    params: list = []
    if q.action:
        sql += " WHERE a.action LIKE ?"
        params.append(f"{q.action}%")
    rows = ctx.db.all(sql + " ORDER BY a.id DESC LIMIT ?", (*params, q.limit))
    for r in rows:
        r["detail"] = jload(r["detail"])
    return rows


@router.get("/admin/roles", summary="Roles and permissions", perm="admin:users")
def roles(ctx: Ctx):
    from ..security import PERMISSIONS

    return {"roles": ROLES, "permissions": {k: sorted(v) for k, v in PERMISSIONS.items()}}
