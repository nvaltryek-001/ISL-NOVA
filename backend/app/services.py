"""Storage, upload validation, audit logging, seeding and the model service."""

from __future__ import annotations

import csv
import hashlib
import logging
import re
import secrets
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .db import Conn, jdump, utcnow
from .security import ROLES, hash_password

log = logging.getLogger("isl_nova")

# --------------------------------------------------------------------------- storage

_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-./]{0,200}$")


class LocalStorage:
    """Object storage adapter backed by a local directory.

    Keys are validated and resolved inside the root so a crafted key can never
    escape it (no absolute paths, no ``..``). A cloud adapter only needs the
    same four methods.
    """

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not _KEY_RE.match(key) or ".." in key.split("/"):
            raise ValueError("invalid storage key")
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise ValueError("invalid storage key")
        return p

    def put(self, key: str, data: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(p)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        try:
            return self._path(key).exists()
        except ValueError:
            return False

    def delete(self, key: str) -> bool:
        p = self._path(key)
        if p.exists():
            p.unlink()
            return True
        return False

    def local_path(self, key: str) -> Path:
        return self._path(key)


# --------------------------------------------------------------------------- uploads

VIDEO_TYPES = {"video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov"}


def sniff_video(head: bytes) -> str | None:
    """Identify a container from magic bytes (never trust the client's MIME type)."""
    if len(head) >= 12 and head[4:8] == b"ftyp":
        brand = head[8:12]
        return "video/quicktime" if brand == b"qt  " else "video/mp4"
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return "video/webm"
    return None


def probe_video(data: bytes, suffix: str) -> dict:
    """Decode with OpenCV to verify the file is a real, readable video."""
    import cv2

    with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
        tmp.write(data)
        tmp.flush()
        cap = cv2.VideoCapture(tmp.name)
        if not cap.isOpened():
            return {"decodable": False}
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        frames, ok = 0, True
        while ok and frames < 3000:
            ok, _ = cap.read()
            frames += int(ok)
        cap.release()
    fps_eff = fps if 1 <= fps <= 240 else 30.0
    return {"decodable": frames > 0, "fps": fps or None, "width": w, "height": h,
            "frames": frames, "duration_s": round(frames / fps_eff, 3) if frames else 0.0}


QUALITY_RULES = {"min_duration_s": 0.5, "max_duration_s": 12.0, "min_width": 320, "min_height": 240,
                 "min_fps": 15.0}


def quality_check(probe: dict) -> dict:
    issues = []
    if not probe.get("decodable"):
        issues.append("file could not be decoded")
    else:
        d = probe.get("duration_s") or 0
        if d < QUALITY_RULES["min_duration_s"]:
            issues.append(f"too short ({d}s)")
        if d > QUALITY_RULES["max_duration_s"]:
            issues.append(f"too long ({d}s) for an isolated sign")
        if probe.get("width", 0) < QUALITY_RULES["min_width"] or probe.get("height", 0) < QUALITY_RULES["min_height"]:
            issues.append(f"resolution {probe.get('width')}x{probe.get('height')} below 320x240")
        if probe.get("fps") and probe["fps"] < QUALITY_RULES["min_fps"]:
            issues.append(f"frame rate {probe['fps']} below 15 fps")
    return {"passed": not issues, "issues": issues, "rules": QUALITY_RULES, **probe}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------- audit

def audit(conn: Conn, actor_id: int | None, action: str, target: str | None = None,
          detail: dict | None = None, ip: str | None = None) -> None:
    conn.insert("audit_logs", {"actor_id": actor_id, "action": action, "target": target,
                               "detail": jdump(detail), "ip": ip, "created_at": utcnow()})


def notify(conn: Conn, user_id: int, title: str, body: str | None = None) -> None:
    conn.insert("notifications", {"user_id": user_id, "title": title, "body": body, "created_at": utcnow()})


# --------------------------------------------------------------------------- seeding

def seed_roles(conn: Conn) -> None:
    for name, desc in ROLES.items():
        if not conn.one("SELECT name FROM roles WHERE name = ?", (name,)):
            conn.insert("roles", {"name": name, "description": desc}, pk=None)


def seed_vocabulary(conn: Conn, vocab_dir: Path) -> int:
    """Load the 200-slot vocabulary CSVs. Existing rows are left untouched so
    reviewer edits made through the API are never overwritten."""
    master = vocab_dir / "signs_master.csv"
    if not master.exists():
        log.warning("vocabulary CSV missing at %s", master)
        return 0
    now = utcnow()
    added = 0
    with master.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    with conn.transaction():
        for r in rows:
            if conn.one("SELECT sign_id FROM signs WHERE sign_id = ?", (r["sign_id"],)):
                continue
            conn.insert("signs", {
                "sign_id": r["sign_id"], "canonical_sign_name": r["canonical_sign_name"],
                "source_gloss": r["source_gloss"], "category": r["category"],
                "category_label": r["category_label"], "source_category": r["source_category"],
                "linguistic_description": r["linguistic_description"] or None,
                "dominant_hand": r["dominant_hand"] or None, "hands_required": r["hands_required"] or None,
                "movement_type": r["movement_type"] or None, "body_movement": r["body_movement"] or None,
                "non_manual_cue": r["non_manual_cue"] or None, "regional_variation": r["regional_variation"] or None,
                "annotation_notes": r["annotation_notes"] or None,
                "verification_status": r["verification_status"], "data_readiness": r["data_readiness"],
                "reviewer": r["reviewer"] or None, "approval_date": r["approval_date"] or None,
                "external_train_videos": int(r["external_train_videos"] or 0),
                "external_val_videos": int(r["external_val_videos"] or 0),
                "external_test_videos": int(r["external_test_videos"] or 0),
                "created_at": now, "updated_at": now}, pk=None)
            added += 1
        tr_path = vocab_dir / "translations.csv"
        if tr_path.exists():
            with tr_path.open(newline="", encoding="utf-8") as fh:
                for t in csv.DictReader(fh):
                    if conn.one("SELECT id FROM translations WHERE sign_id = ? AND language = ?", (t["sign_id"], t["language"])):
                        continue
                    conn.insert("translations", {"sign_id": t["sign_id"], "language": t["language"], "text": t["text"],
                                                 "status": t["status"], "source": t["source"] or None,
                                                 "reviewer": t["reviewer"] or None, "updated_at": now})
        ref_path = vocab_dir / "references.csv"
        if ref_path.exists() and not conn.scalar("SELECT COUNT(*) FROM sign_references"):
            with ref_path.open(newline="", encoding="utf-8") as fh:
                for x in csv.DictReader(fh):
                    conn.insert("sign_references", {
                        "sign_id": x["sign_id"], "source_name": x["source_name"], "source_url": x["source_url"],
                        "doi": x["doi"], "license": x["license"], "media_type": x["media_type"],
                        "training_permitted": x["training_permitted"], "notes": x["notes"],
                        "attribution": "INCLUDE (Sridhar et al., ACM MM 2020), CC BY 4.0"})
    return added


def ensure_user(conn: Conn, email: str, password: str, name: str, roles: list[str], iterations: int) -> int:
    row = conn.one("SELECT id FROM users WHERE email = ?", (email.lower(),))
    if row:
        uid = row["id"]
    else:
        uid = conn.insert("users", {"email": email.lower(), "display_name": name,
                                    "password_hash": hash_password(password, iterations), "created_at": utcnow()})
    for r in roles:
        if not conn.one("SELECT 1 AS x FROM user_roles WHERE user_id = ? AND role_name = ?", (uid, r)):
            conn.insert("user_roles", {"user_id": uid, "role_name": r, "granted_at": utcnow()}, pk=None)
    return uid


def new_code(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4)}"


# --------------------------------------------------------------------------- model + jobs

class ModelService:
    """Loads the active registry model once and reloads on demand."""

    def __init__(self, registry_dir: Path, allow_synthetic: bool):
        self.registry_dir = Path(registry_dir)
        self.allow_synthetic = allow_synthetic
        self._lock = threading.Lock()
        self._predictor = None
        self._error = "not loaded"

    def reload(self) -> None:
        from isl_nova_ml.inference import ModelUnavailable, Predictor

        with self._lock:
            self._predictor, self._error = None, None
            try:
                p = Predictor.from_registry(self.registry_dir)
                if p.synthetic and not self.allow_synthetic:
                    raise ModelUnavailable("active model is a synthetic smoke-test model; refusing to serve it")
                self._predictor = p
            except ModelUnavailable as exc:
                self._error = str(exc)

    @property
    def predictor(self):
        return self._predictor

    @property
    def error(self) -> str | None:
        return self._error


class Jobs:
    """Background executor for long-running work (training, video analysis)."""

    def __init__(self, workers: int = 1):
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="isl-nova-job")

    def submit(self, fn, *args):
        fut = self.pool.submit(fn, *args)
        fut.add_done_callback(lambda f: f.exception() and log.error("job failed: %s", f.exception()))
        return fut

    def shutdown(self):
        self.pool.shutdown(wait=False, cancel_futures=True)
