"""scripts/include_local.py orchestration: checksum-verified, resumable downloads (network faked)."""
import hashlib
import importlib.util
from pathlib import Path

import isl_nova_ml.include_pipeline as ip

SPEC = importlib.util.spec_from_file_location("include_local", Path(__file__).resolve().parents[2] / "scripts" / "include_local.py")
il = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(il)


class _Resp:
    def __init__(self, data, status, drop_after=None):
        self.data, self.status, self.pos, self.drop_after = data, status, 0, drop_after

    def read(self, n):
        if self.drop_after is not None and self.pos >= self.drop_after:
            raise ConnectionResetError("WinError 10054 (simulated)")
        chunk = self.data[self.pos:self.pos + min(n, 100)]
        self.pos += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_download_verify_and_resume(tmp_path, monkeypatch):
    blobs = {"Adjectives_1of8.zip": b"a" * 1000, "Animals_1of2.zip": bytes(range(250)) * 2}
    files = [{"key": k, "size": len(v), "checksum": "md5:" + hashlib.md5(v).hexdigest(), "url": f"https://x/{k}"}  # noqa: S324
             for k, v in blobs.items()]
    calls, drops = [], {"Adjectives_1of8.zip": 2}  # the first part drops the connection twice mid-file

    def fake_urlopen(req, timeout=0):
        key = req.full_url.rsplit("/", 1)[1]
        rng = req.get_header("Range")
        start = int(rng.split("=")[1].rstrip("-")) if rng else 0
        calls.append((key, start))
        drop = None
        if drops.get(key):
            drops[key] -= 1
            drop = 300
        return _Resp(blobs[key][start:], 206 if rng else 200, drop)

    monkeypatch.setattr(ip, "zenodo_files", lambda: ({}, files))
    monkeypatch.setattr(il.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(il.time, "sleep", lambda s: None)
    root = tmp_path / "include"
    assert il.main(["--root", str(root), "--download-only"]) == 0
    # resumed with Range from where each dropped connection stopped, never from zero
    assert [c for c in calls if c[0] == "Adjectives_1of8.zip"] == [("Adjectives_1of8.zip", 0), ("Adjectives_1of8.zip", 300),
                                                                  ("Adjectives_1of8.zip", 600)]
    for f in files:
        assert il.verified(root / "zips" / f["key"], f["size"], f["checksum"])
        assert (root / "zips" / f["key"]).read_bytes() == blobs[f["key"]]

    calls.clear()  # rerun: nothing downloaded again
    assert il.main(["--root", str(root), "--download-only"]) == 0
    assert calls == []

    # an interrupted .partial from an earlier run is continued; a corrupt complete file is replaced
    z = root / "zips"
    (z / "Animals_1of2.zip").unlink()
    (z / "Animals_1of2.zip.ok").unlink()
    (z / "Animals_1of2.zip.partial").write_bytes(blobs["Animals_1of2.zip"][:123])
    (z / "Adjectives_1of8.zip.ok").unlink()
    (z / "Adjectives_1of8.zip").write_bytes(b"x" * 1000)
    assert il.main(["--root", str(root), "--download-only"]) == 0
    assert ("Animals_1of2.zip", 123) in calls and ("Adjectives_1of8.zip", 0) in calls
    for f in files:
        assert (z / f["key"]).read_bytes() == blobs[f["key"]]
