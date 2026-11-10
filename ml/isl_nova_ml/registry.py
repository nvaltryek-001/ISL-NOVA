"""File-based model registry with promotion and rollback.

Layout::

    <root>/registry.json
    <root>/<model_id>/{architecture.json, weights.npz, model.json, metrics.json, training_log.jsonl}

Synthetic smoke-test models can be registered (so the pipeline is testable)
but cannot be promoted to ``production`` unless ``allow_synthetic=True`` is
passed explicitly, which only the automated tests do.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .data import sha256_file


class RegistryError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class Registry:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.path = self.root / "registry.json"

    def read(self) -> dict:
        if not self.path.exists():
            return {"models": [], "active": None, "history": []}
        return json.loads(self.path.read_text())

    def _write(self, data: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self.path)

    def register(self, model_dir: Path) -> dict:
        info = json.loads((model_dir / "model.json").read_text())
        if model_dir.parent.resolve() != self.root.resolve():
            raise RegistryError("model directory must live inside the registry root")
        data = self.read()
        if any(m["model_id"] == info["model_id"] for m in data["models"]):
            raise RegistryError(f"model {info['model_id']} already registered")
        entry = {
            "model_id": info["model_id"], "kind": info["kind"], "created_utc": info["created_utc"],
            "synthetic": info["synthetic"], "status": "candidate", "contract": info["contract"]["name"],
            "dataset_version": info["lineage"].get("dataset_version"),
            "test_top1": info.get("metrics_summary", {}).get("test_top1"),
            "test_macro_f1": info.get("metrics_summary", {}).get("test_macro_f1"),
        }
        data["models"].append(entry)
        self._write(data)
        return entry

    def promote(self, model_id: str, actor: str = "cli", allow_synthetic: bool = False) -> dict:
        data = self.read()
        entry = next((m for m in data["models"] if m["model_id"] == model_id), None)
        if entry is None:
            raise RegistryError(f"unknown model {model_id}")
        if entry["synthetic"] and not allow_synthetic:
            raise RegistryError("synthetic smoke-test models cannot be promoted")
        for m in data["models"]:
            if m["status"] == "production":
                m["status"] = "archived"
        entry["status"] = "production"
        data["history"].append({"ts": _now(), "action": "promote", "model_id": model_id,
                                "previous": data["active"], "actor": actor})
        data["active"] = model_id
        self._write(data)
        return entry

    def rollback(self, actor: str = "cli") -> str | None:
        data = self.read()
        promos = [h for h in data["history"] if h["action"] == "promote"]
        if not promos:
            raise RegistryError("nothing to roll back")
        prev = promos[-1]["previous"]
        for m in data["models"]:
            if m["model_id"] == data["active"]:
                m["status"] = "archived"
            if m["model_id"] == prev:
                m["status"] = "production"
        data["history"].append({"ts": _now(), "action": "rollback", "model_id": prev,
                                "previous": data["active"], "actor": actor})
        data["active"] = prev
        self._write(data)
        return prev

    def active_dir(self) -> Path | None:
        a = self.read().get("active")
        return self.root / a if a else None


def verify_integrity(model_dir: Path) -> None:
    info = json.loads((model_dir / "model.json").read_text())
    want = info.get("weights_sha256")
    if not want or sha256_file(model_dir / "weights.npz") != want:
        raise RegistryError(f"weights checksum mismatch for {info.get('model_id')}")
