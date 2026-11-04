import json
import time

import numpy as np
from app.db import Database
from app.main import create_app
from isl_nova_ml.synthetic import make_sequence, write_synthetic_dataset
from isl_nova_ml.train import run
from starlette.testclient import TestClient

from tests.conftest import Api, make_settings, make_video, verify_sign

A = "/api/v1"


def _signer_with_consent(c, h, scopes=("recording_storage", "model_training")):
    s = c.post(f"{A}/dataset/signers", json={"dominant_hand": "right", "age_band": "26-35"}, headers=h).json()
    assert s["signer_code"].startswith("SGN-")
    r = c.post(f"{A}/dataset/signers/{s['id']}/consents",
               json={"scopes": list(scopes), "confirmed_by_signer": True}, headers=h)
    assert r.status_code == 201, r.text
    sess = c.post(f"{A}/dataset/sessions", json={"signer_id": s["id"], "lighting": "indoor"}, headers=h).json()
    return s, r.json(), sess


def _landmarks(cls=1):
    return json.dumps({"aspect": 4 / 3, "frames": make_sequence(cls, np.random.default_rng(cls), 30)})


def test_consent_is_mandatory(app_env):
    c, api, admin, _ = app_env
    s = c.post(f"{A}/dataset/signers", json={}, headers=admin).json()
    r = c.post(f"{A}/dataset/signers/{s['id']}/consents", json={"scopes": ["recording_storage"],
                                                                "confirmed_by_signer": False}, headers=admin)
    assert r.status_code == 422
    r = c.post(f"{A}/dataset/signers/{s['id']}/consents", json={"scopes": ["model_training"],
                                                                "confirmed_by_signer": True}, headers=admin)
    assert r.status_code == 422, "recording_storage scope must be required"
    assert c.post(f"{A}/dataset/sessions", json={"signer_id": s["id"]}, headers=admin).status_code == 409


def test_recording_upload_validation_and_review_workflow(app_env, tmp_path):
    c, api, admin, settings = app_env
    curator = api.user(admin, "data_curator")
    ling = api.user(admin, "linguist")
    learner = api.user(admin)
    signer, consent, sess = _signer_with_consent(c, curator)
    video = make_video(tmp_path / "v.mp4")

    def up(data, name="v.mp4", sign="ISL005", lm=None, h=curator):
        files = {"file": (name, data, "video/mp4")}
        form = {"sign_id": sign, "session_id": str(sess["id"])}
        if lm:
            form["landmarks"] = lm
        return c.post(f"{A}/dataset/recordings", data=form, files=files, headers=h)

    assert up(video, h=learner).status_code == 403
    assert up(b"not a video at all, just text").status_code == 415
    assert up(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 200).status_code == 422  # magic ok, undecodable
    assert up(video, lm='{"frames": "nope"}').status_code == 422
    r = up(video, lm=_landmarks())
    assert r.status_code == 201, r.text
    rec = r.json()
    assert rec["status"] == "pending_review" and rec["quality"]["passed"] is True
    assert rec["quality"]["landmarks"]["status"] == "ok" and rec["signer_code"] == signer["signer_code"]
    assert up(video).status_code == 409  # exact duplicate
    assert c.get(f"{A}/signs/ISL005").json()["data_readiness"] == "ready_for_review"

    ann = c.post(f"{A}/annotations", json={"recording_id": rec["id"], "label_sign_id": "ISL005",
                                           "start_ms": 100, "end_ms": 900}, headers=curator).json()
    r = c.patch(f"{A}/annotations/{ann['id']}", json={"decision": "approved"}, headers=curator)
    assert r.status_code == 403  # curator lacks review permission
    lead = api.user(admin, "linguist", "data_curator")
    ann2 = c.post(f"{A}/annotations", json={"recording_id": rec["id"], "label_sign_id": "ISL005"}, headers=lead).json()
    assert c.patch(f"{A}/annotations/{ann2['id']}", json={"decision": "approved"}, headers=lead).status_code == 403
    assert c.patch(f"{A}/annotations/{ann['id']}", json={"decision": "approved"}, headers=ling).status_code == 200
    assert c.get(f"{A}/dataset/recordings/{rec['id']}", headers=ling).json()["status"] == "approved"
    assert c.get(f"{A}/signs/ISL005").json()["data_readiness"] == "insufficient_data"
    media = c.get(f"{A}/dataset/recordings/{rec['id']}/media", headers=ling)
    assert media.status_code == 200 and media.headers["cache-control"] == "no-store" and media.content == video
    assert c.get(f"{A}/dataset/recordings/{rec['id']}/media", headers=curator).status_code == 403

    stats = c.get(f"{A}/dataset/stats").json()
    assert stats["classes_with_recordings"] == 1 and stats["approved_samples"] == 1
    assert stats["classes_approved_for_training"] == 0
    table = {r["sign_id"]: r for r in c.get(f"{A}/dataset/signs", headers=curator).json()}
    assert table["ISL005"]["approved"] == 1 and table["ISL005"]["signers"] == 1

    v = c.post(f"{A}/dataset/validate", headers=curator).json()
    assert v["ok"] is True and v["recordings_checked"] == 1
    assert any(i["check"] == "signer_independence" for i in v["issues"])

    ver = c.post(f"{A}/dataset/versions", json={"version": "0.1.0", "description": "first"}, headers=curator)
    assert ver.status_code == 201, ver.text
    assert ver.json()["summary"]["recordings"] == 1
    assert c.post(f"{A}/dataset/versions", json={"version": "0.1.0", "description": "again"},
                  headers=curator).status_code == 409
    man = c.get(f"{A}/dataset/versions/{ver.json()['id']}/manifest", headers=curator).json()
    assert man["entries"][0]["sign_id"] == "ISL005" and man["entries"][0]["consent_scope"] == ["model_training",
                                                                                                "recording_storage"]

    # withdrawal of consent erases media and updates readiness
    r = c.post(f"{A}/dataset/consents/{consent['id']}/revoke", json={"reason": "signer request"}, headers=curator)
    assert r.json()["recordings_erased"] == 1
    assert c.get(f"{A}/dataset/recordings/{rec['id']}", headers=curator).json()["status"] == "deleted"
    assert not (settings.storage_dir / rec["storage_key"]).exists()
    assert c.get(f"{A}/signs/ISL005").json()["data_readiness"] == "no_data"


def test_version_requires_training_consent(app_env, tmp_path):
    c, api, admin, _ = app_env
    ling = api.user(admin, "linguist")
    _, _, sess = _signer_with_consent(c, admin, scopes=("recording_storage",))
    rec = c.post(f"{A}/dataset/recordings", data={"sign_id": "ISL007", "session_id": str(sess["id"]),
                                                  "landmarks": _landmarks()},
                 files={"file": ("v.mp4", make_video(tmp_path / "a.mp4"), "video/mp4")}, headers=admin).json()
    ann = c.post(f"{A}/annotations", json={"recording_id": rec["id"], "label_sign_id": "ISL007"}, headers=admin).json()
    c.patch(f"{A}/annotations/{ann['id']}", json={"decision": "approved"}, headers=ling)
    r = c.post(f"{A}/dataset/versions", json={"version": "1.0.0", "description": "first try"}, headers=admin)
    assert r.status_code == 409 and r.json()["error"]["code"] == "no_eligible_recordings"


def test_validation_flags_expired_retention(app_env, tmp_path):
    c, api, admin, settings = app_env
    s = c.post(f"{A}/dataset/signers", json={}, headers=admin).json()
    c.post(f"{A}/dataset/signers/{s['id']}/consents", json={"scopes": ["recording_storage"], "confirmed_by_signer": True,
                                                             "retention_until": "2099-01-01"}, headers=admin)
    sess = c.post(f"{A}/dataset/sessions", json={"signer_id": s["id"]}, headers=admin).json()
    r = c.post(f"{A}/dataset/recordings", data={"sign_id": "ISL009", "session_id": str(sess["id"])},
               files={"file": ("v.mp4", make_video(tmp_path / "r.mp4", seed=9), "video/mp4")}, headers=admin)
    assert r.status_code == 201
    assert not any(i["check"] == "retention_expired" for i in c.post(f"{A}/dataset/validate", headers=admin).json()["issues"])
    with Database(settings.database_url).connect() as conn:
        conn.execute("UPDATE consent_records SET retention_until = ?", ("2020-01-01T00:00:00Z",))
    v = c.post(f"{A}/dataset/validate", headers=admin).json()
    assert v["ok"] is False and any(i["check"] == "retention_expired" for i in v["issues"])


def test_signer_erasure(app_env, tmp_path):
    c, api, admin, settings = app_env
    s, _, sess = _signer_with_consent(c, admin)
    rec = c.post(f"{A}/dataset/recordings", data={"sign_id": "ISL008", "session_id": str(sess["id"])},
                 files={"file": ("v.mp4", make_video(tmp_path / "b.mp4", seed=3), "video/mp4")}, headers=admin).json()
    r = c.delete(f"{A}/dataset/signers/{s['id']}", headers=admin).json()
    assert r["recordings_erased"] == 1 and r["tombstoned"] is False
    assert not (settings.storage_dir / rec["storage_key"]).exists()
    assert all(x["id"] != s["id"] for x in c.get(f"{A}/dataset/signers", headers=admin).json())


def test_prediction_without_model_is_honest(app_env):
    c, *_ = app_env
    frames = make_sequence(1, np.random.default_rng(1), 30)
    r = c.post(f"{A}/predict/sequence", json={"frames": frames}).json()
    assert r == {"state": "model_unavailable", "top": [], "reasons": ["no active model in registry"]}
    assert c.get(f"{A}/model/metrics").json()["available"] is False
    assert c.get(f"{A}/evaluation/confusion-matrix").json()["matrix"] == []
    bad = c.post(f"{A}/predict/sequence", json={"frames": [{"left": [[0, 0, 0]] * 5}]})
    assert bad.status_code == 422


def _train_synthetic(settings):
    root = settings.storage_dir.parent / "syn"
    write_synthetic_dataset(root, n_classes=4, n_signers=5, reps=3)
    return run({"model": "pooled_logreg"}, root / "manifest.json", root, settings.model_registry_dir, None, "syn")


def test_synthetic_model_is_refused_unless_explicitly_allowed(app_env):
    c, api, admin, settings = app_env
    res = _train_synthetic(settings)
    r = c.post(f"{A}/models/{res['model_id']}/promote", headers=admin)
    assert r.status_code == 409 and "synthetic" in r.json()["error"]["message"]
    reg = c.get(f"{A}/models", headers=admin).json()
    assert reg["models"][0]["synthetic"] is True and reg["active"] is None


def test_inference_states_with_explicitly_allowed_synthetic_model(tmp_path):
    settings = make_settings(tmp_path, allow_synthetic_model=True)
    res = _train_synthetic(settings)
    with TestClient(create_app(settings)) as c:
        api = Api(c)
        admin = api.login("admin@example.org", "admin-password-1")
        learner = api.user(admin)
        assert c.post(f"{A}/models/{res['model_id']}/promote", headers=learner).status_code == 403
        info = c.post(f"{A}/models/{res['model_id']}/promote", headers=admin).json()
        assert info["available"] and info["synthetic"] is True and "NOT ISL" in info["warning"]
        frames = make_sequence(2, np.random.default_rng(5), 40)
        out = c.post(f"{A}/predict/sequence", json={"frames": frames, "aspect": 4 / 3, "save_to_history": True},
                     headers=learner).json()
        assert out["state"] in {"recognized", "uncertain", "unknown"} and out["synthetic"] is True
        assert len(out["top"]) == 4 and out["top"][0]["sign_id"].startswith("SYN")
        assert c.get(f"{A}/history", headers=learner).json()[0]["id"] == out["history_id"]
        empty = c.post(f"{A}/predict", json={"frames": [{"left": None, "right": None, "pose": None}] * 12}).json()
        assert empty["state"] == "insufficient_input"
        m = c.get(f"{A}/model/metrics").json()
        assert m["synthetic"] is True and 0 <= m["test"]["top1"] <= 1
        cm = c.get(f"{A}/evaluation/confusion-matrix").json()
        assert len(cm["matrix"]) == len(cm["labels"]) == 4
        rb = c.post(f"{A}/models/rollback", headers=admin).json()
        assert rb["available"] is False


def test_experiments(app_env):
    c, api, admin, _ = app_env
    res = api.user(admin, "researcher")
    learner = api.user(admin)
    body = {"name": "lstm baseline", "model_kind": "lstm", "config": {"hidden": 32}}
    assert c.post(f"{A}/experiments", json=body, headers=learner).status_code == 403
    assert c.post(f"{A}/experiments", json={**body, "config": {"rm -rf": 1}}, headers=res).status_code == 422
    e = c.post(f"{A}/experiments", json=body, headers=res).json()
    r = c.post(f"{A}/experiments/{e['id']}/run", headers=res).json()
    assert r["status"] == "blocked" and "dataset version" in r["error"]
    assert c.get(f"{A}/experiments", headers=res).json()[0]["id"] == e["id"]


def test_history_feedback_learning_phrases(app_env):
    c, api, admin, _ = app_env
    ling = api.user(admin, "linguist")
    u = api.user(admin)
    hid = c.post(f"{A}/history", json={"state": "uncertain", "top": [{"sign_id": "ISL001"}]}, headers=u).json()["id"]
    assert c.patch(f"{A}/history/{hid}", json={"state": "uncertain", "corrected_sign": "ISL002"},
                   headers=u).status_code == 200
    other = api.user(admin)
    assert c.delete(f"{A}/history/{hid}", headers=other).status_code == 404
    assert c.delete(f"{A}/history", headers=u).json()["deleted"] == 1

    assert c.post(f"{A}/feedback", json={"kind": "content", "message": "Sign ISL004 needs review",
                                         "sign_id": "ISL004"}).status_code == 201
    fb = c.get(f"{A}/feedback", headers=ling).json()
    assert c.patch(f"{A}/feedback/{fb[0]['id']}", json={"status": "resolved"}, headers=ling).json()["status"] == "resolved"
    assert c.get(f"{A}/feedback", headers=u).status_code == 403

    les = c.get(f"{A}/learning/lessons").json()
    assert les["verified_signs"] == 0 and les["lessons"] == []
    assert len(c.get(f"{A}/learning/lessons", params={"include_unverified": True}).json()["lessons"]) == 12
    assert c.get(f"{A}/learning/quiz").json()["available"] is False
    for sid, word in (("ISL020", "Hello"), ("ISL021", "How are you")):
        verify_sign(c, sid, ling)
        c.put(f"{A}/signs/{sid}/translations/en", json={"text": word, "status": "verified"}, headers=ling)
    qz = c.get(f"{A}/learning/quiz", params={"n": 2}).json()
    assert qz["available"] and len(qz["questions"]) == 2 and len(qz["questions"][0]["options"]) == 2
    for ok in (True, False, False):
        c.post(f"{A}/learning/attempts", json={"sign_id": "ISL020", "mode": "quiz", "correct": ok}, headers=u)
    p = c.get(f"{A}/learning/progress", headers=u).json()
    assert p["attempts"] == 3 and p["correct"] == 1 and p["difficult"][0]["sign_id"] == "ISL020"

    assert c.post(f"{A}/phrases", json={"sign_ids": ["ISL001"], "text": "x", "is_quick": True},
                  headers=ling).status_code == 422  # ISL001 not verified
    assert c.post(f"{A}/phrases", json={"sign_ids": ["ISL020"], "text": "Hello", "is_quick": True},
                  headers=u).status_code == 403
    assert c.post(f"{A}/phrases", json={"sign_ids": ["ISL020", "ISL021"], "text": "Hello. How are you?",
                                        "is_quick": True}, headers=ling).status_code == 201
    pid = c.post(f"{A}/phrases", json={"sign_ids": ["ISL001"], "text": "alright"}, headers=u).json()["id"]
    ph = c.get(f"{A}/phrases", headers=u).json()
    assert {p["text"] for p in ph} == {"Hello. How are you?", "alright"}
    assert c.delete(f"{A}/phrases/{pid}", headers=other).status_code == 403
    assert c.delete(f"{A}/phrases/{pid}", headers=u).status_code == 200
    d = c.get(f"{A}/dashboard", headers=u).json()
    assert d["dataset"]["class_slots"] == 200 and d["model"]["available"] is False and d["me"]["attempts"] == 3


def test_video_analysis_job(app_env, tmp_path):
    c, api, admin, _ = app_env
    u = api.user(admin)
    assert c.post(f"{A}/analysis/videos", files={"file": ("x.txt", b"hello", "text/plain")},
                  headers=u).status_code == 415
    j = c.post(f"{A}/analysis/videos", files={"file": ("v.mp4", make_video(tmp_path / "z.mp4"), "video/mp4")},
               headers=u).json()
    for _ in range(50):
        r = c.get(f"{A}/analysis/videos/{j['id']}", headers=u).json()
        if r["status"] not in ("queued", "processing"):
            break
        time.sleep(0.1)
    assert r["status"] == "extractor_unavailable"
    assert r["result"]["video"]["decodable"] is True and r["result"]["predictions"] == []
    assert c.get(f"{A}/analysis/videos/{j['id']}", headers=api.user(admin)).status_code == 404
    assert c.delete(f"{A}/analysis/videos/{j['id']}", headers=u).status_code == 200


def test_new_signer_evaluation_run(tmp_path):
    """Exercise the evaluation-run workflow end to end (synthetic model: code path only)."""
    settings = make_settings(tmp_path, allow_synthetic_model=True)
    root = settings.storage_dir.parent / "syn"
    write_synthetic_dataset(root, n_classes=3, n_signers=4, reps=2, unknown_classes=0)
    m = json.loads((root / "manifest.json").read_text())
    for e in m["entries"]:  # classes map onto vocabulary ids so local recordings can reference them
        e["sign_id"] = "ISL%03d" % int(e["sign_id"][3:])
    (root / "manifest.json").write_text(json.dumps(m))
    res = run({"model": "pooled_logreg"}, root / "manifest.json", root, settings.model_registry_dir, None, "syn")
    with TestClient(create_app(settings)) as c:
        api = Api(c)
        admin = api.login("admin@example.org", "admin-password-1")
        assert c.post(f"{A}/evaluation/runs", json={"dataset_version_id": 1}, headers=admin).status_code == 409
        c.post(f"{A}/models/{res['model_id']}/promote", headers=admin)
        assert c.post(f"{A}/evaluation/runs", json={"dataset_version_id": 99}, headers=admin).status_code == 404
        # a "new signer" records two consented clips with landmarks; a second reviewer approves them
        ling = api.user(admin, "linguist")
        s, _, sess = _signer_with_consent(c, admin)
        for i, sid in enumerate(("ISL001", "ISL002")):
            frames = make_sequence(int(sid[-1]), np.random.default_rng(40 + i), 40)
            rec = c.post(f"{A}/dataset/recordings", data={"sign_id": sid, "session_id": str(sess["id"]),
                                                          "landmarks": json.dumps({"aspect": 4 / 3, "frames": frames})},
                         files={"file": ("v.mp4", make_video(tmp_path / f"n{i}.mp4", seed=60 + i), "video/mp4")},
                         headers=admin).json()
            ann = c.post(f"{A}/annotations", json={"recording_id": rec["id"], "label_sign_id": sid}, headers=admin).json()
            c.patch(f"{A}/annotations/{ann['id']}", json={"decision": "approved"}, headers=ling)
        v = c.post(f"{A}/dataset/versions", json={"version": "9.0.0", "description": "new signer eval"}, headers=admin).json()
        r = c.post(f"{A}/evaluation/runs", json={"dataset_version_id": v["id"], "note": "new signer"}, headers=admin).json()
        assert r["report"]["status"] == "running"
        for _ in range(50):
            got = c.get(f"{A}/evaluation/runs/{r['id']}", headers=admin).json()
            if got["report"]["status"] != "running":
                break
            time.sleep(0.1)
        rep = got["report"]
        assert rep["status"] == "completed", rep
        assert rep["overall"]["n"] == 2 and rep["signers"] == 1 and s["signer_code"] in rep["per_signer"]
        assert len(rep["rows"]) == 2 and "rows" not in c.get(f"{A}/evaluation/runs", headers=admin).json()[0]["report"]
        assert c.get(f"{A}/evaluation/runs", headers=api.user(admin)).status_code == 403
