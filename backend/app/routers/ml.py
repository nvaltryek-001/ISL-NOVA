"""AI Laboratory: model info, inference, evaluation, registry and experiments."""

from __future__ import annotations

import json
import traceback

from pydantic import BaseModel, Field, field_validator

from ..api import ApiError, Ctx, Router, not_found
from ..db import jdump, jload, utcnow
from ..services import audit

router = Router("ml")

Point = list[float]


class FrameIn(BaseModel):
    left: list[Point] | None = None
    right: list[Point] | None = None
    pose: list[Point] | None = None

    @field_validator("left", "right")
    @classmethod
    def _hand(cls, v):
        if v is not None and (len(v) != 21 or any(len(p) < 3 for p in v)):
            raise ValueError("hand must have 21 points of [x, y, z]")
        return v

    @field_validator("pose")
    @classmethod
    def _pose(cls, v):
        if v is not None and (len(v) != 33 or any(len(p) < 3 for p in v)):
            raise ValueError("pose must have 33 points of [x, y, z(, visibility)]")
        return v


class PredictIn(BaseModel):
    frames: list[FrameIn] = Field(max_length=300)
    aspect: float = Field(default=4 / 3, gt=0.2, lt=5)
    top_k: int = Field(default=5, ge=1, le=10)
    save_to_history: bool = False


class ExperimentIn(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    model_kind: str = Field(pattern="^(lstm|gru|pooled_logreg|dtw_1nn)$")
    dataset_version_id: int | None = None
    config: dict = Field(default_factory=dict)


SAFE_CONFIG_KEYS = {"hidden", "epochs", "batch_size", "lr", "weight_decay", "patience", "lr_decay", "lr_patience",
                    "augment", "seed", "min_train_samples", "class_weighting", "tau_keep", "margin", "dtw_window",
                    "logreg_C"}


def _info(ctx: Ctx) -> dict:
    from isl_nova_ml.contract import as_dict

    ms = ctx.app.models
    p = ms.predictor
    base = {"feature_contract": as_dict()}
    if p is None:
        return {"available": False, "state": "model_unavailable",
                "reason": ms.error or "no trained model has been promoted", **base}
    info = p.info
    return {"available": True, "state": "ready", "model_id": info["model_id"], "kind": info["kind"],
            "synthetic": p.synthetic, "warning": info.get("warning"), "created_utc": info["created_utc"],
            "classes": info["classes"], "n_classes": len(info["classes"]), "thresholds": info["thresholds"],
            "lineage": {k: info["lineage"].get(k) for k in ("dataset_version", "split_counts", "split_policy")},
            "metrics_summary": info.get("metrics_summary"), **base}


@router.get("/model/info", summary="Active model status (never fabricated)", auth="none")
def model_info(ctx: Ctx):
    return _info(ctx)


@router.get("/model/metrics", summary="Held-out metrics of the active model", auth="none")
def model_metrics(ctx: Ctx):
    p = ctx.app.models.predictor
    if p is None:
        return {"available": False, "reason": "no active model; no metrics exist"}
    m = json.loads((p.dir / "metrics.json").read_text())
    return {"available": True, "synthetic": p.synthetic, "model_id": p.info["model_id"],
            "test": {k: v for k, v in m["test"].items() if k not in ("confusion", "per_class")},
            "validation": {k: v for k, v in m["validation"].items() if k not in ("confusion", "per_class")},
            "open_set": m.get("open_set"), "per_signer_test": m.get("per_signer_test"),
            "latency_ms_per_sample_batch": m.get("latency_ms_per_sample_batch"),
            "model_size_bytes": m.get("model_size_bytes")}


@router.get("/evaluation/metrics", summary="Per-class held-out evaluation", auth="none")
def evaluation_metrics(ctx: Ctx):
    p = ctx.app.models.predictor
    if p is None:
        return {"available": False, "per_class": []}
    m = json.loads((p.dir / "metrics.json").read_text())
    labels = {c["index"]: c for c in p.classes}
    pcs = [{**d, "sign_id": labels[d["class"]]["sign_id"], "label": labels[d["class"]]["label"]}
           for d in m["test"]["per_class"]]
    return {"available": True, "synthetic": p.synthetic, "per_class": pcs}


@router.get("/evaluation/confusion-matrix", summary="Test-set confusion matrix", auth="none")
def confusion(ctx: Ctx):
    p = ctx.app.models.predictor
    if p is None:
        return {"available": False, "labels": [], "matrix": []}
    m = json.loads((p.dir / "metrics.json").read_text())
    return {"available": True, "synthetic": p.synthetic, "labels": [c["sign_id"] for c in p.classes],
            "matrix": m["test"]["confusion"]}


def _predict(ctx: Ctx) -> dict:
    p = ctx.app.models.predictor
    b: PredictIn = ctx.body
    if p is None:
        return {"state": "model_unavailable", "top": [], "reasons": [ctx.app.models.error or "no active model"]}
    frames = [f.model_dump() for f in b.frames]
    out = p.predict(frames, b.aspect, b.top_k)
    # attach verified meanings only; unverified glosses are labelled as such
    from .signs import translations_for

    tr = translations_for(ctx.db, [t["sign_id"] for t in out["top"]])
    for t in out["top"]:
        t["meanings"] = {lang: v for lang, v in tr.get(t["sign_id"], {}).items() if v["text"]}
    if b.save_to_history and ctx.user:
        chosen = out["top"][0]["sign_id"] if out["state"] == "recognized" else None
        if chosen and not ctx.db.one("SELECT sign_id FROM signs WHERE sign_id = ?", (chosen,)):
            chosen = None  # e.g. synthetic smoke-test classes are not vocabulary entries
        hid = ctx.db.insert("recognition_history", {"user_id": ctx.uid, "model_id": out.get("model_id"),
                                                    "state": out["state"], "top": jdump(out["top"][:5]),
                                                    "chosen_sign": chosen,
                                                    "created_at": utcnow()})
        out["history_id"] = hid
    return out


@router.post("/predict/sequence", summary="Classify a landmark sequence", auth="optional", body=PredictIn,
             rate="default")
def predict_sequence(ctx: Ctx):
    return _predict(ctx)


@router.post("/predict", summary="Classify the current window (alias of /predict/sequence)", auth="optional",
             body=PredictIn, rate="default")
def predict(ctx: Ctx):
    return _predict(ctx)


# --------------------------------------------------------------------------- registry

def sync_registry(ctx_or_state, conn) -> list[dict]:
    from isl_nova_ml.registry import Registry

    reg = Registry(ctx_or_state.settings.model_registry_dir).read()
    for m in reg["models"]:
        vals = {"kind": m["kind"], "dataset_version": m.get("dataset_version"), "contract_name": m["contract"],
                "synthetic": bool(m["synthetic"]), "status": m["status"],
                "summary": jdump({"test_top1": m.get("test_top1"), "test_macro_f1": m.get("test_macro_f1")})}
        if conn.one("SELECT model_id FROM model_versions WHERE model_id = ?", (m["model_id"],)):
            conn.update("model_versions", vals, "model_id = ?", (m["model_id"],))
        else:
            conn.insert("model_versions", {"model_id": m["model_id"], **vals, "registered_at": m["created_utc"]}, pk=None)
    return reg["models"]


@router.get("/models", summary="Model registry", perm="experiments:read")
def models(ctx: Ctx):
    from isl_nova_ml.registry import Registry

    sync_registry(ctx.app, ctx.db)
    reg = Registry(ctx.app.settings.model_registry_dir).read()
    rows = ctx.db.all("SELECT * FROM model_versions ORDER BY registered_at DESC")
    for r in rows:
        r["summary"] = jload(r["summary"])
        r["synthetic"] = bool(r["synthetic"])
    return {"active": reg["active"], "models": rows, "history": reg["history"][-20:]}


@router.post("/models/{model_id}/promote", summary="Promote a model to production", perm="models:promote")
def promote(ctx: Ctx):
    from isl_nova_ml.registry import Registry, RegistryError

    mid = ctx.params["model_id"]
    try:
        Registry(ctx.app.settings.model_registry_dir).promote(mid, ctx.user["email"],
                                                              allow_synthetic=ctx.app.settings.allow_synthetic_model)
    except RegistryError as exc:
        raise ApiError(409, "promotion_refused", str(exc)) from exc
    ctx.app.models.reload()
    sync_registry(ctx.app, ctx.db)
    audit(ctx.db, ctx.uid, "model.promote", mid, ip=ctx.ip)
    return _info(ctx)


@router.post("/models/rollback", summary="Roll back to the previously active model", perm="models:promote")
def rollback(ctx: Ctx):
    from isl_nova_ml.registry import Registry, RegistryError

    try:
        prev = Registry(ctx.app.settings.model_registry_dir).rollback(ctx.user["email"])
    except RegistryError as exc:
        raise ApiError(409, "rollback_refused", str(exc)) from exc
    ctx.app.models.reload()
    sync_registry(ctx.app, ctx.db)
    audit(ctx.db, ctx.uid, "model.rollback", str(prev), ip=ctx.ip)
    return _info(ctx)


# --------------------------------------------------------------------------- experiments

def _exp(ctx: Ctx, eid: int) -> dict:
    e = ctx.db.one("SELECT * FROM experiments WHERE id = ?", (eid,))
    if not e:
        raise not_found("experiment")
    e["config"] = jload(e["config"])
    e["metrics"] = ctx.db.all("SELECT split, name, value, epoch FROM experiment_metrics WHERE experiment_id = ? "
                              "ORDER BY id", (eid,))
    return e


@router.get("/experiments", summary="Experiments", perm="experiments:read")
def list_experiments(ctx: Ctx):
    rows = ctx.db.all("SELECT e.*, d.version AS dataset_version FROM experiments e LEFT JOIN dataset_versions d "
                      "ON d.id = e.dataset_version_id ORDER BY e.id DESC LIMIT 100")
    for r in rows:
        r["config"] = jload(r["config"])
    return rows


@router.get("/experiments/{eid}", summary="Experiment detail", perm="experiments:read")
def get_experiment(ctx: Ctx):
    return _exp(ctx, int(ctx.params["eid"]))


@router.post("/experiments", summary="Register an experiment configuration", perm="experiments:write",
             body=ExperimentIn, status=201)
def create_experiment(ctx: Ctx):
    b: ExperimentIn = ctx.body
    bad = set(b.config) - SAFE_CONFIG_KEYS
    if bad:
        raise ApiError(422, "validation_error", f"unsupported config keys {sorted(bad)}")
    if b.dataset_version_id and not ctx.db.one("SELECT id FROM dataset_versions WHERE id = ?", (b.dataset_version_id,)):
        raise not_found("dataset version")
    eid = ctx.db.insert("experiments", {"name": b.name, "model_kind": b.model_kind,
                                        "config": jdump({**b.config, "model": b.model_kind, "experiment_name": b.name}),
                                        "dataset_version_id": b.dataset_version_id, "created_by": ctx.uid,
                                        "created_at": utcnow()})
    audit(ctx.db, ctx.uid, "experiment.create", str(eid), ip=ctx.ip)
    return _exp(ctx, eid)


@router.post("/experiments/{eid}/run", summary="Queue a training run (background job)", perm="experiments:write")
def run_experiment(ctx: Ctx):
    eid = int(ctx.params["eid"])
    e = _exp(ctx, eid)
    if e["status"] in ("queued", "running"):
        raise ApiError(409, "already_running", "experiment already queued or running")
    if not e["dataset_version_id"]:
        ctx.db.update("experiments", {"status": "blocked", "error": "no dataset version selected; create one from "
                                      "approved, consented recordings first"}, "id = ?", (eid,))
        return _exp(ctx, eid)
    ctx.db.update("experiments", {"status": "queued", "error": None, "log": ""}, "id = ?", (eid,))
    audit(ctx.db, ctx.uid, "experiment.run", str(eid), ip=ctx.ip)
    ctx.app.jobs.submit(_train_job, ctx.app, eid)
    return _exp(ctx, eid)


def _train_job(state, eid: int) -> None:
    from isl_nova_ml.train import TrainingError, run

    from .dataset import _manifest_for_version

    log_lines: list[str] = []
    with state.db.connect() as conn:
        e = conn.one("SELECT * FROM experiments WHERE id = ?", (eid,))
        conn.update("experiments", {"status": "running", "started_at": utcnow()}, "id = ?", (eid,))
        try:
            fake = type("C", (), {"db": conn, "app": state})()
            manifest = _manifest_for_version(fake, e["dataset_version_id"])
            mpath = state.settings.storage_dir / "manifests" / f"experiment-{eid}.json"
            mpath.parent.mkdir(parents=True, exist_ok=True)
            mpath.write_text(json.dumps(manifest))
            res = run(jload(e["config"]), mpath, state.settings.storage_dir, state.settings.model_registry_dir,
                      state.settings.vocab_csv, manifest["dataset_version"], log=log_lines.append)
            for k, v in res["summary"].items():
                conn.insert("experiment_metrics", {"experiment_id": eid, "split": k.split("_")[0], "name": k,
                                                   "value": v})
            conn.update("experiments", {"status": "succeeded", "model_id": res["model_id"], "finished_at": utcnow(),
                                        "log": "\n".join(log_lines[-400:])}, "id = ?", (eid,))
            sync_registry(state, conn)
        except TrainingError as exc:
            conn.update("experiments", {"status": "blocked", "error": str(exc), "finished_at": utcnow(),
                                        "log": "\n".join(log_lines[-400:])}, "id = ?", (eid,))
        except Exception as exc:  # noqa: BLE001
            conn.update("experiments", {"status": "failed", "error": f"{exc}\n{traceback.format_exc()[-2000:]}",
                                        "finished_at": utcnow(), "log": "\n".join(log_lines[-400:])}, "id = ?", (eid,))
