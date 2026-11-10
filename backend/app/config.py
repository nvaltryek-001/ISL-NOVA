"""Runtime configuration from environment variables (see .env.example)."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _bool(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    env: str = "development"
    database_url: str = f"sqlite:///{REPO / 'storage' / 'isl_nova.db'}"
    jwt_secret: str = ""
    jwt_ttl_minutes: int = 120
    refresh_ttl_days: int = 30
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:5173", "http://localhost:8000"])
    storage_dir: Path = REPO / "storage" / "objects"
    model_registry_dir: Path = REPO / "artifacts" / "models"
    references_dir: Path = REPO / "dataset" / "references"
    vocab_csv: Path = REPO / "dataset" / "vocabulary" / "signs_master.csv"
    vocab_dir: Path = REPO / "dataset" / "vocabulary"
    frontend_dist: Path = REPO / "frontend" / "dist"
    max_upload_mb: int = 50
    pbkdf2_iterations: int = 600_000
    allow_synthetic_model: bool = False
    allow_open_registration: bool = True
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None
    analysis_retention_hours: int = 24
    storage_backend: str = "local"  # local | s3
    s3_endpoint: str | None = None
    s3_bucket: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_region: str = "us-east-1"
    redis_url: str | None = None
    vocabulary_limit: int = 200  # the project is fixed at 200 signs; 0 = no limit
    history_retention_days: int = 0  # 0 = keep until the user deletes it
    notification_retention_days: int = 180
    retention_interval_hours: float = 24
    rate_limit_per_minute: int = 120
    auth_rate_limit_per_minute: int = 10
    hand_model_path: str | None = None
    pose_model_path: str | None = None

    @classmethod
    def from_env(cls, **overrides) -> Settings:
        e = os.environ
        s = cls(
            env=e.get("ISL_NOVA_ENV", "development"),
            database_url=e.get("DATABASE_URL", cls.database_url),
            jwt_secret=e.get("JWT_SECRET", ""),
            jwt_ttl_minutes=int(e.get("JWT_TTL_MINUTES", "120")),
            refresh_ttl_days=int(e.get("REFRESH_TTL_DAYS", "30")),
            cors_origins=[o.strip() for o in e.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:8000").split(",") if o.strip()],
            storage_dir=Path(e.get("STORAGE_DIR", str(cls.storage_dir))),
            model_registry_dir=Path(e.get("MODEL_REGISTRY_DIR", str(cls.model_registry_dir))),
            references_dir=Path(e.get("REFERENCES_DIR", str(cls.references_dir))),
            max_upload_mb=int(e.get("MAX_UPLOAD_MB", "50")),
            pbkdf2_iterations=int(e.get("PBKDF2_ITERATIONS", "600000")),
            allow_synthetic_model=_bool(e.get("ALLOW_SYNTHETIC_MODEL")),
            allow_open_registration=_bool(e.get("ALLOW_OPEN_REGISTRATION"), True),
            bootstrap_admin_email=e.get("BOOTSTRAP_ADMIN_EMAIL") or None,
            bootstrap_admin_password=e.get("BOOTSTRAP_ADMIN_PASSWORD") or None,
            analysis_retention_hours=int(e.get("ANALYSIS_RETENTION_HOURS", "24")),
            vocabulary_limit=int(e.get("VOCABULARY_LIMIT", "200")),
            storage_backend=e.get("STORAGE_BACKEND", "local"),
            s3_endpoint=e.get("S3_ENDPOINT") or None, s3_bucket=e.get("S3_BUCKET") or None,
            s3_access_key=e.get("S3_ACCESS_KEY") or None, s3_secret_key=e.get("S3_SECRET_KEY") or None,
            s3_region=e.get("S3_REGION", "us-east-1"),
            redis_url=e.get("REDIS_URL") or None,
            history_retention_days=int(e.get("HISTORY_RETENTION_DAYS", "0")),
            notification_retention_days=int(e.get("NOTIFICATION_RETENTION_DAYS", "180")),
            retention_interval_hours=float(e.get("RETENTION_INTERVAL_HOURS", "24")),
            rate_limit_per_minute=int(e.get("RATE_LIMIT_PER_MINUTE", "120")),
            auth_rate_limit_per_minute=int(e.get("AUTH_RATE_LIMIT_PER_MINUTE", "10")),
            hand_model_path=e.get("ISL_NOVA_HAND_MODEL") or None,
            pose_model_path=e.get("ISL_NOVA_POSE_MODEL") or None,
        )
        if "FRONTEND_DIST" in e:
            s.frontend_dist = Path(e["FRONTEND_DIST"])
        for k, v in overrides.items():
            setattr(s, k, v)
        s.validate()
        return s

    def validate(self) -> None:
        if self.env == "production":
            if len(self.jwt_secret) < 32:
                raise RuntimeError("JWT_SECRET must be set to >= 32 characters in production")
            if self.allow_synthetic_model:
                raise RuntimeError("ALLOW_SYNTHETIC_MODEL is not permitted in production")
            if "*" in self.cors_origins:
                raise RuntimeError("wildcard CORS is not permitted in production")
        if not self.jwt_secret:
            # development only: ephemeral secret, tokens die on restart
            self.jwt_secret = secrets.token_urlsafe(48)
