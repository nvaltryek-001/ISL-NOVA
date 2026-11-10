"""English / Hindi / Kannada meanings: coverage, review sheet export and bulk import.

Machine-drafted meanings are stored with status ``draft``. Only the linguist
role may set ``verified``; an import never downgrades or overwrites a verified
row unless a linguist performs it.
"""

from __future__ import annotations

import csv
import io

from starlette.responses import Response

from ..api import ApiError, Ctx, Router
from ..db import utcnow
from ..services import audit

router = Router("translations")
LANGS = ("en", "hi", "kn")
STATUSES = ("pending", "source_gloss", "draft", "verified", "rejected")
SHEET_COLS = ["sign_id", "canonical_sign_name", "category", "language", "text", "transliteration", "status",
              "source", "reviewer", "reviewed_at", "new_text", "new_transliteration", "new_status", "review_notes"]


def coverage(db) -> dict:
    out = {lang: {s: 0 for s in STATUSES} | {"with_text": 0} for lang in LANGS}
    for r in db.all("SELECT language, status, COUNT(*) AS n, SUM(CASE WHEN text <> '' THEN 1 ELSE 0 END) AS t "
                    "FROM translations GROUP BY language, status"):
        if r["language"] in out and r["status"] in out[r["language"]]:
            out[r["language"]][r["status"]] = int(r["n"])
            out[r["language"]]["with_text"] += int(r["t"] or 0)
    total = db.scalar("SELECT COUNT(*) FROM signs WHERE retired = ?", (False,)) or 0
    return {"signs": int(total), "languages": out}


@router.get("/translations/coverage", summary="Meanings per language and review status", auth="optional")
def get_coverage(ctx: Ctx):
    return coverage(ctx.db)


@router.get("/translations/review-sheet.csv", summary="CSV of all en/hi/kn meanings for native-speaker review",
            perm="translations:write")
def review_sheet(ctx: Ctx):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(SHEET_COLS)
    rows = ctx.db.all(
        "SELECT t.sign_id, s.canonical_sign_name, s.category_label, t.language, t.text, t.transliteration, t.status, "
        "t.source, t.reviewer, t.reviewed_at FROM translations t JOIN signs s ON s.sign_id = t.sign_id "
        "ORDER BY t.sign_id, t.language")
    for r in rows:
        w.writerow([r["sign_id"], r["canonical_sign_name"], r["category_label"], r["language"], r["text"],
                    r["transliteration"] or "", r["status"], r["source"] or "", r["reviewer"] or "",
                    r["reviewed_at"] or "", "", "", "", ""])
    audit(ctx.db, ctx.uid, "translation.review_sheet_export", None, {"rows": len(rows)}, ctx.ip)
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="isl-nova-translations-review.csv"'})


@router.post("/translations/import", summary="Apply a reviewed translation sheet (new_text / new_status columns)",
             perm="translations:write", multipart=True)
def import_sheet(ctx: Ctx):
    upload = ctx.form.get("file") if ctx.form else None
    if upload is None or isinstance(upload, str):
        raise ApiError(422, "validation_error", "upload the reviewed CSV as 'file'")
    raw = upload.file.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise ApiError(413, "too_large", "review sheet must be under 2 MB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ApiError(422, "validation_error", "the sheet must be UTF-8 CSV") from exc
    is_linguist = "linguist" in ctx.roles
    applied, skipped, errors = 0, 0, []
    now = utcnow()
    for i, r in enumerate(csv.DictReader(io.StringIO(text)), start=2):
        sid, lang = (r.get("sign_id") or "").strip(), (r.get("language") or "").strip()
        new_text = (r.get("new_text") or "").strip()
        new_status = (r.get("new_status") or "").strip()
        new_tr = (r.get("new_transliteration") or "").strip()
        if not (new_text or new_status or new_tr):
            skipped += 1
            continue
        if lang not in LANGS:
            errors.append({"row": i, "error": "language must be en, hi or kn"})
            continue
        cur = ctx.db.one("SELECT * FROM translations WHERE sign_id = ? AND language = ?", (sid, lang))
        if not cur:
            errors.append({"row": i, "error": f"unknown sign/language {sid}/{lang}"})
            continue
        status = new_status or ("draft" if new_text else cur["status"])
        if status not in ("draft", "verified", "rejected"):
            errors.append({"row": i, "error": "new_status must be draft, verified or rejected"})
            continue
        if status == "verified" and not is_linguist:
            errors.append({"row": i, "error": "only a linguist can mark a meaning verified"})
            continue
        if cur["status"] == "verified" and not is_linguist:
            errors.append({"row": i, "error": "verified meanings can only be changed by a linguist"})
            continue
        final_text = new_text or cur["text"]
        if status == "verified" and not final_text:
            errors.append({"row": i, "error": "a verified meaning needs text"})
            continue
        vals = {"text": final_text, "status": status, "updated_at": now, "source": "human review sheet",
                "transliteration": new_tr or cur["transliteration"]}
        if status in ("verified", "rejected"):
            vals |= {"reviewer": ctx.user["display_name"], "reviewed_at": now}
        ctx.db.update("translations", vals, "id = ?", (cur["id"],))
        applied += 1
    audit(ctx.db, ctx.uid, "translation.import", None, {"applied": applied, "errors": len(errors)}, ctx.ip)
    return {"applied": applied, "skipped": skipped, "errors": errors[:200], "coverage": coverage(ctx.db)}
