"""S3-compatible storage against a real server (MinIO in CI). Skipped unless S3_TEST_ENDPOINT is set."""
import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("S3_TEST_ENDPOINT"), reason="set S3_TEST_ENDPOINT (MinIO) to run")


def _store(tmp_path):
    from app.storage_s3 import S3Storage
    st = S3Storage(os.environ["S3_TEST_ENDPOINT"], "isl-nova-test-" + uuid.uuid4().hex[:8],
                   os.environ.get("S3_TEST_ACCESS_KEY", "minioadmin"), os.environ.get("S3_TEST_SECRET_KEY", "minioadmin"),
                   cache_dir=tmp_path / "cache")
    st.ensure_bucket()
    return st


def test_put_get_exists_delete_and_local_path(tmp_path):
    st = _store(tmp_path)
    key = "recordings/ISL001/a b+c.mp4"
    assert not st.exists(key)
    st.put(key, b"\x00\x01video")
    assert st.exists(key) and st.get(key) == b"\x00\x01video"
    p = st.local_path(key)
    assert p.read_bytes() == b"\x00\x01video"
    p2 = st.local_path("landmarks/new.npz")
    p2.write_bytes(b"npz")
    st.sync("landmarks/new.npz")
    assert st.get("landmarks/new.npz") == b"npz"
    root = st.materialize([key])
    assert (root / key).exists()
    assert st.delete(key) is True and not st.exists(key)
    with pytest.raises(FileNotFoundError):
        st.get(key)
    with pytest.raises(ValueError):
        st.put("../escape", b"x")


def test_app_runs_on_s3_storage(tmp_path):
    from app.main import create_app
    from starlette.testclient import TestClient

    from tests.conftest import make_settings
    s = make_settings(tmp_path, storage_backend="s3", s3_endpoint=os.environ["S3_TEST_ENDPOINT"],
                      s3_bucket="isl-nova-app-" + uuid.uuid4().hex[:8],
                      s3_access_key=os.environ.get("S3_TEST_ACCESS_KEY", "minioadmin"),
                      s3_secret_key=os.environ.get("S3_TEST_SECRET_KEY", "minioadmin"))
    with TestClient(create_app(s)) as c:
        h = c.get("/api/v1/health").json()
        assert h["status"] == "ok" and h["storage"] == "S3Storage"
