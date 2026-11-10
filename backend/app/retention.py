"""Data-retention job.

Deletes data whose retention window has passed and reports what needs a human
decision. Raw dataset recordings are never deleted automatically: recordings
whose consent retention date has passed are only reported, so a data curator can
review them (deletion goes through the existing erasure workflow).

    python -m app.manage retention            # dry run: counts only
    python -m app.manage retention --apply    # delete

The server also runs it with --apply every RETENTION_INTERVAL_HOURS (default 24,
0 disables).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from .db import Conn, utcnow

log = logging.getLogger("isl_nova.retention")


def _ago(days: float) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_retention(conn: Conn, settings, storage=None, apply: bool = False) -> dict:
    now = utcnow()
    rules: list[tuple[str, str, tuple]] = [
        ("password_resets_expired_or_used",
         "FROM password_resets WHERE expires_at < ? OR used_at IS NOT NULL", (now,)),
        ("refresh_tokens_expired_or_revoked",
         "FROM refresh_tokens WHERE expires_at < ? OR revoked_at IS NOT NULL OR used_at IS NOT NULL", (now,)),
        ("notifications_read_old",
         "FROM notifications WHERE read_at IS NOT NULL AND created_at < ?",
         (_ago(settings.notification_retention_days),)),
    ]
    if settings.history_retention_days > 0:
        rules.append(("recognition_history_old", "FROM recognition_history WHERE created_at < ?",
                      (_ago(settings.history_retention_days),)))
    out: dict = {"applied": apply, "time": now, "deleted" if apply else "would_delete": {}}
    key = "deleted" if apply else "would_delete"
    for name, where, params in rules:
        n = int(conn.one(f"SELECT COUNT(*) AS n {where}", params)["n"])  # noqa: S608 - fixed SQL, bound params
        if apply and n:
            conn.execute(f"DELETE {where}", params)  # noqa: S608
        out[key][name] = n

    # expired video-analysis uploads: delete the stored file, keep the job row as "expired"
    jobs = conn.all("SELECT id, storage_key FROM analysis_jobs WHERE expires_at < ? AND storage_key IS NOT NULL",
                    (now,))
    if apply:
        for j in jobs:
            if storage is not None:
                try:
                    storage.delete(j["storage_key"])
                except (ValueError, OSError):
                    pass
            conn.update("analysis_jobs", {"storage_key": None, "status": "expired"}, "id = ?", (j["id"],))
    out[key]["analysis_uploads_expired"] = len(jobs)

    today = now[:10]
    expired = conn.all("SELECT r.recording_code, cr.retention_until FROM recordings r JOIN consent_records cr "
                       "ON cr.id = r.consent_id WHERE cr.retention_until IS NOT NULL AND r.status <> 'deleted'")
    out["needs_review"] = {"recordings_past_consent_retention":
                           [r["recording_code"] for r in expired if str(r["retention_until"])[:10] < today]}
    if apply:
        log.info("retention %s", out)
    return out
