import pytest
from app.config import Settings
from app.db import Database
from app.migrate import MigrationError, migrate, status
from app.services import LocalStorage

from tests.conftest import CHECKLIST, DESCRIBED

A = "/api/v1"


def test_health_and_openapi(app_env):
    c, *_ = app_env
    h = c.get(f"{A}/health").json()
    assert h["status"] == "ok" and h["model"]["available"] is False
    spec = c.get(f"{A}/openapi.json").json()
    for p in ("/api/v1/signs", "/api/v1/predict/sequence", "/api/v1/dataset/recordings", "/api/v1/auth/login"):
        assert p in spec["paths"]
    assert c.get(f"{A}/nope").status_code == 404


def test_security_headers_and_cors(app_env):
    c, *_ = app_env
    r = c.get(f"{A}/health", headers={"Origin": "https://evil.example"})
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert "access-control-allow-origin" not in r.headers
    ok = c.get(f"{A}/health", headers={"Origin": "http://localhost:5173"})
    assert ok.headers["access-control-allow-origin"] == "http://localhost:5173"
    d = c.get("/api/docs")
    assert "swagger-ui-dist@5.17.14" in d.text and "<script>" not in d.text  # no inline script under CSP
    assert "https://cdn.jsdelivr.net" in d.headers["content-security-policy"]
    js = c.get("/api/docs/init.js")
    assert js.status_code == 200 and "SwaggerUIBundle" in js.text


def test_register_login_and_profile(app_env):
    c, api, admin, _ = app_env
    r = c.post(f"{A}/auth/register", json={"email": "X@Example.org", "password": "short", "display_name": "x"})
    assert r.status_code == 422
    r = c.post(f"{A}/auth/register", json={"email": "new@example.org", "password": "long-enough-pw",
                                           "display_name": "New"})
    assert r.status_code == 201 and r.json()["user"]["roles"] == ["learner"]
    assert c.post(f"{A}/auth/register", json={"email": "NEW@example.org", "password": "long-enough-pw",
                                              "display_name": "dup"}).status_code == 409
    assert c.post(f"{A}/auth/login", json={"email": "new@example.org", "password": "wrong-password"}).status_code == 401
    h = api.login("new@example.org", "long-enough-pw")
    assert c.get(f"{A}/me").status_code == 401
    assert c.get(f"{A}/me", headers={"Authorization": "Bearer garbage"}).status_code == 401
    me = c.patch(f"{A}/me", json={"preferred_language": "kn", "settings": {"high_contrast": True, "evil": 1}},
                 headers=h).json()
    assert me["preferred_language"] == "kn" and me["settings"] == {"high_contrast": True}
    bad = c.patch(f"{A}/me", json={"current_password": "nope", "new_password": "another-long-pw"}, headers=h)
    assert bad.status_code == 400


def test_login_rate_limit(tmp_path):
    from app.main import create_app
    from starlette.testclient import TestClient

    from tests.conftest import make_settings

    with TestClient(create_app(make_settings(tmp_path, auth_rate_limit_per_minute=3))) as c:
        codes = [c.post(f"{A}/auth/login", json={"email": "a@b.co", "password": "x"}).status_code for _ in range(5)]
    assert codes[:3] == [401, 401, 401] and codes[3:] == [429, 429]


def test_vocabulary_has_200_unverified_slots(app_env):
    c, *_ = app_env
    r = c.get(f"{A}/signs", params={"size": 200}).json()
    assert r["total"] == 200
    ids = [s["sign_id"] for s in r["items"]]
    assert ids == [f"ISL{i:03d}" for i in range(1, 201)]
    assert all(s["verification_status"] == "reference_found" for s in r["items"])
    assert all(s["data_readiness"] == "no_data" for s in r["items"])
    # Hindi/Kannada are machine drafts: present, but never presented as verified
    for lang in ("hi", "kn"):
        assert all(s["translations"][lang]["status"] == "draft" and s["translations"][lang]["text"] for s in r["items"])
        assert all("machine" in (s["translations"][lang]["source"] or "") for s in r["items"])
    stats = c.get(f"{A}/dataset/stats").json()
    assert stats["class_slots"] == 200 and stats["verified_classes"] == 0
    assert stats["classes_with_recordings"] == 0 and stats["approved_samples"] == 0


def test_search_and_filters(app_env):
    c, *_ = app_env
    r = c.get(f"{A}/signs", params={"q": "good morning"}).json()
    assert [s["canonical_sign_name"] for s in r["items"]] == ["Good Morning"]
    cats = c.get(f"{A}/signs/categories").json()
    assert sum(x["slots"] for x in cats) == 200
    r = c.get(f"{A}/signs", params={"category": "people_family"}).json()
    assert r["total"] == 20 and all(s["category"] == "people_family" for s in r["items"])
    assert c.get(f"{A}/signs", params={"size": 999}).status_code == 422
    d = c.get(f"{A}/signs/ISL001").json()
    assert d["references"][0]["license"] == "CC BY 4.0" and d["related"]
    assert c.get(f"{A}/signs/ISL999").status_code == 404


def test_rbac_on_sign_writes(app_env):
    c, api, admin, _ = app_env
    learner = api.user(admin)
    body = {"sign_id": "ISL201", "canonical_sign_name": "Water", "category": "daily_needs", "english_meaning": "water"}
    assert c.post(f"{A}/signs", json=body, headers=learner).status_code == 403
    assert c.post(f"{A}/signs", json=body).status_code == 401
    assert c.get(f"{A}/admin/users", headers=learner).status_code == 403


def test_sign_crud_lifecycle(app_env):
    c, api, admin, _ = app_env
    body = {"sign_id": "ISL201", "canonical_sign_name": "Water", "category": "daily_needs", "english_meaning": "water",
            "hands_required": "one", "movement_type": "dynamic"}
    r = c.post(f"{A}/signs", json=body, headers=admin)
    assert r.status_code == 201 and r.json()["verification_status"] == "proposed"
    assert c.post(f"{A}/signs", json=body, headers=admin).status_code == 409
    assert c.post(f"{A}/signs", json={**body, "sign_id": "X1"}, headers=admin).status_code == 422
    r = c.patch(f"{A}/signs/ISL201", json={"annotation_notes": "two variants seen"}, headers=admin)
    assert r.json()["annotation_notes"] == "two variants seen"
    assert c.delete(f"{A}/signs/ISL201", headers=admin).json()["retired"] is True
    assert c.get(f"{A}/signs", params={"q": "water"}).json()["total"] == 0
    assert c.get(f"{A}/signs", params={"q": "water", "include_retired": True}).json()["total"] == 1
    assert c.post(f"{A}/signs/ISL201/restore", headers=admin).json()["retired"] is False


def test_verification_workflow_requires_linguist(app_env):
    c, api, admin, _ = app_env
    ling = api.user(admin, "linguist", name="Dr Linguist")
    r = c.post(f"{A}/signs/ISL001/review", json={"to_status": "verified", "note": "skip"}, headers=ling)
    assert r.status_code == 409 and "review_pending" in r.json()["error"]["details"]["allowed"]
    assert c.post(f"{A}/signs/ISL001/review", json={"to_status": "review_pending", "note": "start"},
                  headers=admin).status_code == 200
    r = c.post(f"{A}/signs/ISL001/review", json={"to_status": "verified", "note": "looks right"}, headers=admin)
    assert r.status_code == 403 and r.json()["error"]["code"] == "linguist_required"
    r = c.post(f"{A}/signs/ISL001/review", json={"to_status": "verified", "note": "matches reference"}, headers=ling)
    assert r.status_code == 422 and r.json()["error"]["code"] == "incomplete_entry"
    assert set(r.json()["error"]["details"]["missing_fields"]) == {"linguistic_description", "hands_required", "movement_type"}
    c.patch(f"{A}/signs/ISL001", json=DESCRIBED, headers=ling)
    r = c.post(f"{A}/signs/ISL001/review", json={"to_status": "verified", "note": "matches reference",
                                                 "checklist": {**CHECKLIST, "meaning_confirmed": False}}, headers=ling)
    assert r.status_code == 422 and r.json()["error"]["code"] == "checklist_incomplete"
    r = c.post(f"{A}/signs/ISL001/review", json={"to_status": "verified", "note": "matches reference",
                                                 "checklist": CHECKLIST}, headers=ling)
    d = r.json()
    assert d["verification_status"] == "verified" and d["reviewer"] == "Dr Linguist" and d["approval_date"]
    assert c.get(f"{A}/dataset/stats").json()["verified_classes"] == 1
    # substantive edit after verification sends it back to review
    d = c.patch(f"{A}/signs/ISL001", json={"hands_required": "two", "movement_type": "static"}, headers=ling).json()
    assert d["verification_status"] == "review_pending"
    assert [e["to_status"] for e in d["verification_events"]][:3] == ["review_pending", "verified", "review_pending"]


def test_translations(app_env):
    c, api, admin, _ = app_env
    ling = api.user(admin, "linguist")
    r = c.put(f"{A}/signs/ISL002/translations/hi", json={"text": "बुरा", "status": "draft"}, headers=admin)
    assert r.status_code == 200 and r.json()["hi"]["status"] == "draft"
    assert c.put(f"{A}/signs/ISL002/translations/hi", json={"text": "बुरा", "status": "verified"},
                 headers=admin).status_code == 403
    assert c.put(f"{A}/signs/ISL002/translations/hi", json={"text": "बुरा", "status": "verified"},
                 headers=ling).json()["hi"]["status"] == "verified"
    assert c.put(f"{A}/signs/ISL002/translations/fr", json={"text": "x", "status": "draft"},
                 headers=ling).status_code == 422
    assert c.get(f"{A}/signs", params={"q": "बुरा"}).json()["items"][0]["sign_id"] == "ISL002"


def test_references_and_bookmarks(app_env):
    c, api, admin, _ = app_env
    r = c.post(f"{A}/signs/ISL003/references", json={"source_name": "Lab recording", "license": "CC BY 4.0",
                                                     "source_url": "https://example.org/x"}, headers=admin)
    assert r.status_code == 201
    assert c.post(f"{A}/signs/ISL003/references", json={"source_name": "x", "license": "y",
                                                         "source_url": "javascript:alert(1)"}, headers=admin).status_code == 422
    assert c.delete(f"{A}/signs/ISL003/references/{r.json()['id']}", headers=admin).status_code == 200
    u = api.user(admin)
    c.put(f"{A}/bookmarks/ISL010", headers=u)
    assert [b["sign_id"] for b in c.get(f"{A}/bookmarks", headers=u).json()] == ["ISL010"]
    assert c.get(f"{A}/signs/ISL010", headers=u).json()["bookmarked"] is True
    c.delete(f"{A}/bookmarks/ISL010", headers=u)
    assert c.get(f"{A}/bookmarks", headers=u).json() == []


def test_admin_roles_and_audit(app_env):
    c, api, admin, _ = app_env
    users = c.get(f"{A}/admin/users", headers=admin).json()
    me = next(u for u in users if u["email"] == "admin@example.org")
    assert c.patch(f"{A}/admin/users/{me['id']}", json={"roles": ["learner"]}, headers=admin).status_code == 400
    assert c.patch(f"{A}/admin/users/{me['id']}", json={"roles": ["wizard"]}, headers=admin).status_code == 422
    log = c.get(f"{A}/admin/audit", headers=admin).json()
    assert any(e["action"] == "auth.login" for e in log)
    assert "permissions" in c.get(f"{A}/admin/roles", headers=admin).json()


def test_deactivated_user_cannot_use_token(app_env):
    c, api, admin, _ = app_env
    u = api.user(admin)
    uid = c.get(f"{A}/me", headers=u).json()["id"]
    c.patch(f"{A}/admin/users/{uid}", json={"is_active": False}, headers=admin)
    assert c.get(f"{A}/me", headers=u).status_code == 401


def test_migrations_idempotent_and_tamper_detected(tmp_path, monkeypatch):
    db = Database(f"sqlite:///{tmp_path / 'm.db'}")
    assert migrate(db) == ["0001_core", "0002_translations_v2", "0003_sign_proposals", "0004_token_version"]
    assert migrate(db) == []
    assert status(db)["pending"] == []
    with db.connect() as conn:
        conn.execute("UPDATE schema_migrations SET checksum = 'x'")
    with pytest.raises(MigrationError):
        migrate(db)


def test_storage_rejects_path_traversal(tmp_path):
    s = LocalStorage(tmp_path)
    for bad in ("../x", "/etc/passwd", "a/../../b", "", ".hidden"):
        with pytest.raises(ValueError):
            s.put(bad, b"x")
    s.put("ok/file.bin", b"data")
    assert s.get("ok/file.bin") == b"data" and s.delete("ok/file.bin")


def test_production_settings_are_strict(monkeypatch):
    monkeypatch.setenv("ISL_NOVA_ENV", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        Settings.from_env()
    monkeypatch.setenv("JWT_SECRET", "s" * 40)
    monkeypatch.setenv("ALLOW_SYNTHETIC_MODEL", "1")
    with pytest.raises(RuntimeError, match="SYNTHETIC"):
        Settings.from_env()


def test_review_sheet_export(app_env):
    c, api, admin, _ = app_env
    learner = api.user(admin)
    assert c.get(f"{A}/signs/review-sheet.csv", headers=learner).status_code == 403
    r = c.get(f"{A}/signs/review-sheet.csv", headers=admin)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert len(lines) == 201 and lines[0].startswith("sign_id,name,category,status")
    assert lines[1].startswith("ISL001,")


def test_prometheus_metrics(app_env, monkeypatch):
    c, *_ = app_env
    c.get(f"{A}/health")
    c.post(f"{A}/predict/sequence", json={"frames": []})
    r = c.get("/metrics")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    body = r.text
    assert 'isl_nova_http_requests_total{method="GET",route="/api/v1/health",status="2xx"}' in body
    assert "isl_nova_http_request_seconds_bucket" in body and "isl_nova_vocabulary_signs 200" in body
    assert "isl_nova_model_available 0" in body
