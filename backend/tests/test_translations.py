"""Three-language meanings: coverage, review sheet, import permissions."""
import csv
import io

A = "/api/v1"


def test_coverage_counts_drafts_not_verified(app_env):
    c, *_ = app_env
    cov = c.get(f"{A}/translations/coverage").json()
    assert cov["signs"] == 200
    for lang in ("hi", "kn"):
        assert cov["languages"][lang]["draft"] == 200
        assert cov["languages"][lang]["verified"] == 0
    assert cov["languages"]["en"]["source_gloss"] == 200


def _sheet(c, h):
    r = c.get(f"{A}/translations/review-sheet.csv", headers=h)
    assert r.status_code == 200
    return list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))


def _upload(c, h, rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
    return c.post(f"{A}/translations/import", files={"file": ("sheet.csv", buf.getvalue().encode(), "text/csv")}, headers=h)


def test_review_sheet_and_import_rules(app_env):
    c, api, admin, _ = app_env
    learner = api.user(admin)
    assert c.get(f"{A}/translations/review-sheet.csv", headers=learner).status_code == 403
    rows = _sheet(c, admin)
    assert len(rows) == 600 and {r["language"] for r in rows} == {"en", "hi", "kn"}
    hi = next(r for r in rows if r["sign_id"] == "ISL012" and r["language"] == "hi")
    assert hi["text"] == "नमस्ते" and hi["status"] == "draft"

    # an admin (not linguist) may correct a draft but not verify it
    edit = dict(hi, new_text="नमस्कार", new_status="")
    verify = dict(hi, new_text="", new_status="verified")
    r = _upload(c, admin, [edit, verify]).json()
    assert r["applied"] == 1 and len(r["errors"]) == 1 and "linguist" in r["errors"][0]["error"]
    t = c.get(f"{A}/signs/ISL012").json()["translations"]["hi"]
    assert t["text"] == "नमस्कार" and t["status"] == "draft"

    ling = api.user(admin, "linguist")
    r = _upload(c, ling, [verify]).json()
    assert r["applied"] == 1 and not r["errors"]
    t = c.get(f"{A}/signs/ISL012").json()["translations"]["hi"]
    assert t["status"] == "verified" and t["reviewer"]
    assert c.get(f"{A}/translations/coverage").json()["languages"]["hi"]["verified"] == 1
    # a verified row is protected from non-linguists
    r = _upload(c, admin, [dict(hi, new_text="x", new_status="draft")]).json()
    assert r["applied"] == 0 and "linguist" in r["errors"][0]["error"]
