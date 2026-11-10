"""The storage interface used by the app is the same for local and S3 backends."""
import pytest
from app.services import LocalStorage, make_storage


def test_local_storage_interface(tmp_path):
    st = LocalStorage(tmp_path)
    st.put("a/b.bin", b"x")
    p = st.local_path("c/d.npz")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"y")
    st.sync("c/d.npz")
    assert st.get("c/d.npz") == b"y" and st.materialize(["a/b.bin"]) == tmp_path.resolve()
    with pytest.raises(ValueError):
        st.put("../x", b"")


def test_make_storage_rejects_unknown_backend(tmp_path):
    from app.config import Settings
    s = Settings.from_env(storage_dir=tmp_path, storage_backend="ftp")
    with pytest.raises(ValueError):
        make_storage(s)
    s3 = Settings.from_env(storage_dir=tmp_path, storage_backend="s3")
    with pytest.raises(ValueError):  # missing endpoint/bucket/keys
        make_storage(s3)
