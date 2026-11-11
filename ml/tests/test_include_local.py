"""scripts/include_local.py orchestration: checksum-verified, resumable downloads (network faked)."""
import hashlib
import importlib.util
from pathlib import Path

import isl_nova_ml.include_pipeline as ip

SPEC = importlib.util.spec_from_file_location("include_local", Path(__file__).resolve().parents[2] / "scripts" / "include_local.py")
il = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(il)


def test_download_verify_and_resume(tmp_path, monkeypatch):
    blobs = {"Adjectives_1of8.zip": b"a" * 1000, "Animals_1of2.zip": b"b" * 500}
    files = [{"key": k, "size": len(v), "checksum": "md5:" + hashlib.md5(v).hexdigest(), "url": f"https://x/{k}"}  # noqa: S324
             for k, v in blobs.items()]
    calls = []

    def fake_download(url, dest, checksum, retries=6):
        key = url.rsplit("/", 1)[1]
        calls.append(key)
        Path(dest).write_bytes(blobs[key])
        return {"bytes": len(blobs[key]), "mb_per_s": 1.0}

    monkeypatch.setattr(ip, "zenodo_files", lambda: ({}, files))
    monkeypatch.setattr(ip, "download", fake_download)
    root = tmp_path / "include"
    assert il.main(["--root", str(root), "--download-only"]) == 0
    assert sorted(calls) == sorted(blobs)
    assert all(il.verified(root / "zips" / f["key"], f["size"], f["checksum"]) for f in files)

    calls.clear()  # rerun: nothing downloaded again
    assert il.main(["--root", str(root), "--download-only"]) == 0
    assert calls == []

    # a complete file without its marker is verified, not re-downloaded; a corrupt one is replaced
    (root / "zips" / "Animals_1of2.zip.ok").unlink()
    (root / "zips" / "Adjectives_1of8.zip.ok").unlink()
    (root / "zips" / "Adjectives_1of8.zip").write_bytes(b"x" * 1000)
    assert il.main(["--root", str(root), "--download-only", "--only", "Adjectives,Animals"]) == 0
    assert calls == ["Adjectives_1of8.zip"]
    assert (root / "zips" / "Adjectives_1of8.zip").read_bytes() == blobs["Adjectives_1of8.zip"]
