import itertools
import os
from pathlib import Path

import cv2
import numpy as np
import pytest
from app.config import Settings
from app.main import create_app
from starlette.testclient import TestClient

_counter = itertools.count()


def _database_url(tmp: Path) -> str:
    """SQLite by default; set TEST_DATABASE_URL=postgresql://... to run the suite on PostgreSQL."""
    pg = os.environ.get("TEST_DATABASE_URL")
    if not pg:
        return f"sqlite:///{tmp / 'db.sqlite'}"
    import psycopg

    with psycopg.connect(pg, autocommit=True) as c:  # fresh schema for every test
        c.execute("DROP SCHEMA public CASCADE")
        c.execute("CREATE SCHEMA public")
    return pg


def make_settings(tmp: Path, **kw) -> Settings:
    base = dict(database_url=_database_url(tmp), storage_dir=tmp / "objects",
                model_registry_dir=tmp / "models", pbkdf2_iterations=1000, jwt_secret="t" * 40,
                bootstrap_admin_email="admin@example.org", bootstrap_admin_password="admin-password-1",
                frontend_dist=tmp / "no-dist", rate_limit_per_minute=10_000, auth_rate_limit_per_minute=10_000)
    base.update(kw)
    return Settings.from_env(**base)


class Api:
    def __init__(self, client: TestClient):
        self.c = client

    def login(self, email, password):
        r = self.c.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def user(self, admin_h, *roles, name=None):
        n = next(_counter)
        email = f"user{n}@example.org"
        r = self.c.post("/api/v1/auth/register", json={"email": email, "password": "password-123!",
                                                         "display_name": name or f"User {n}"})
        assert r.status_code == 201, r.text
        uid = r.json()["user"]["id"]
        if roles:
            r = self.c.patch(f"/api/v1/admin/users/{uid}", json={"roles": list(roles)}, headers=admin_h)
            assert r.status_code == 200, r.text
        return self.login(email, "password-123!")


@pytest.fixture
def app_env(tmp_path):
    settings = make_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        api = Api(client)
        admin = api.login("admin@example.org", "admin-password-1")
        yield client, api, admin, settings


def make_video(path: Path, seconds: float = 1.0, size=(320, 240), fps=30, seed=0) -> bytes:
    rng = np.random.default_rng(seed)
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    for i in range(int(seconds * fps)):
        frame = np.full((size[1], size[0], 3), 40, np.uint8)
        cv2.circle(frame, (40 + i * 3 % 240, 120), 20, (int(rng.integers(0, 255)), 180, 90), -1)
        vw.write(frame)
    vw.release()
    return path.read_bytes()
