"""Download the full INCLUDE video dataset and extract landmarks on your own computer.

    python scripts/include_local.py                    # everything: download, extract (hands, pose, face), merge
    python scripts/include_local.py --download-only    # only fetch and verify the 56.8 GB of zips
    python scripts/include_local.py --workers 4        # more parallel extraction processes (CPU cores)
    python scripts/include_local.py --only Adjectives  # a subset (zip names or category prefixes)

What it does, in order (each step is resumable: rerun after an interruption and finished work is skipped):
  1. reads the Zenodo record of INCLUDE (doi:10.1145/3394171.3413528, CC BY 4.0) and checks free disk space
  2. downloads every zip part into <root>/zips, verifying the MD5 published by Zenodo (kept, unless --delete-zips)
  3. downloads the MediaPipe hand, pose and face task files if missing
  4. extracts landmarks from each part in parallel (feature contract 2.0.0: hands + pose + 22 face points),
     including the 63 reserve glosses used only as open-set "unknown sign" data
  5. merges all parts into <root>/landmarks-face-v1 (manifest.json + .npz files, no video)

Then train on it:
    python scripts/train_local.py --data data/include/landmarks-face-v1 --model bilstm-attn-face --promote

Videos are INCLUDE's; keep its attribution and licence (dataset/sources/include) with anything derived.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "ml")]

TASKS = {
    "hand_landmarker.task": "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
    "pose_landmarker_lite.task": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
    "face_landmarker.task": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
}
GB = 1e9


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def file_hash(path: Path, algo: str) -> str:
    h = hashlib.new(algo)
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 22):
            h.update(chunk)
    return h.hexdigest()


def verified(zp: Path, size: int, checksum: str) -> bool:
    """A zip counts as done when it has the right size and a .ok marker holding the verified checksum."""
    ok = zp.with_suffix(zp.suffix + ".ok")
    return zp.exists() and zp.stat().st_size == size and ok.exists() and ok.read_text().strip() == checksum


def fetch_part(meta: dict, zips: Path) -> str:
    from isl_nova_ml.include_pipeline import download

    zp = zips / meta["key"]
    if verified(zp, meta["size"], meta["checksum"]):
        return "already verified"
    if zp.exists() and zp.stat().st_size == meta["size"]:  # complete file without a marker: verify instead of re-downloading
        algo, _, want = meta["checksum"].partition(":")
        log(f"verifying existing {meta['key']} ...")
        if file_hash(zp, algo or "md5") == want:
            zp.with_suffix(zp.suffix + ".ok").write_text(meta["checksum"])
            return "verified existing file"
        zp.unlink()
    tmp = zp.with_suffix(zp.suffix + ".partial")
    r = download(meta["url"], tmp, meta["checksum"])  # MD5-checked while streaming; retries with back-off
    tmp.replace(zp)
    zp.with_suffix(zp.suffix + ".ok").write_text(meta["checksum"])
    return f"downloaded {r['bytes'] / GB:.2f} GB at {r['mb_per_s']} MB/s"


def extract_part(meta: dict, zips: Path, parts: Path, work: Path, tasks: Path, face: bool, max_side: int) -> str:
    out = parts / meta["key"].replace(" ", "_")
    if (out / "part_manifest.json").exists():
        return "already extracted"
    shutil.rmtree(out, ignore_errors=True)
    wdir = work / meta["key"].replace(" ", "_")
    shutil.rmtree(wdir, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "isl_nova_ml.include_pipeline", "extract-part", "--part", meta["key"],
           "--zip", str(zips / meta["key"]), "--out", str(out), "--work", str(wdir),
           "--hand-model", str(tasks / "hand_landmarker.task"), "--pose-model", str(tasks / "pose_landmarker_lite.task"),
           "--max-side", str(max_side), "--include-reserve"]
    if face:
        cmd += ["--face-model", str(tasks / "face_landmarker.task")]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "ml"), str(ROOT / "backend")]), "PYTHONIOENCODING": "utf-8"}
    t0 = time.time()
    with (out / "extract.log").open("w", encoding="utf-8") as lf:
        rc = subprocess.run(cmd, cwd=ROOT, env=env, stdout=lf, stderr=subprocess.STDOUT).returncode  # noqa: S603
    shutil.rmtree(wdir, ignore_errors=True)
    if rc != 0 or not (out / "part_manifest.json").exists():
        (out / "part_manifest.json").unlink(missing_ok=True)
        raise RuntimeError(f"extraction failed (exit {rc}); see {out / 'extract.log'}")
    rep = json.loads((out / "part_manifest.json").read_text())["report"]
    return (f"{rep['processed']} vocabulary + {rep.get('reserve_processed', 0)} reserve videos, "
            f"{rep['failed']} failed, {(time.time() - t0) / 60:.1f} min")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=ROOT / "data" / "include", help="where zips, parts and the merged dataset go")
    ap.add_argument("--only", default="", help="comma-separated zip names or category prefixes (default: all parts)")
    ap.add_argument("--workers", type=int, default=max(1, min(4, (os.cpu_count() or 2) // 2)),
                    help="parallel extraction processes (default: half the CPU cores, at most 4)")
    ap.add_argument("--no-face", action="store_true", help="hands + pose only (contract 1.0.0), faster")
    ap.add_argument("--max-side", type=int, default=960, help="resize frames so the longer side is at most this")
    ap.add_argument("--download-only", action="store_true")
    ap.add_argument("--delete-zips", action="store_true", help="delete each zip after its landmarks are extracted")
    ap.add_argument("--version", default="include-face-v1", help="dataset version written to the manifest")
    a = ap.parse_args(argv)

    from isl_nova_ml.include_pipeline import zenodo_files

    zips, parts, work = a.root / "zips", a.root / "parts", a.root / "work"
    merged = a.root / ("landmarks-face-v1" if not a.no_face else "landmarks-v1-local")
    tasks = ROOT / "artifacts" / "mediapipe"
    for d in (zips, parts, work, tasks):
        d.mkdir(parents=True, exist_ok=True)

    log("reading the INCLUDE record on Zenodo ...")
    rec, files = zenodo_files()
    allp = [f for f in files if f["key"].endswith(".zip")]
    if a.only:
        want = {w.strip() for w in a.only.split(",") if w.strip()}
        allp = [p for p in allp if p["key"] in want or p["key"].split("_")[0] in want]
    if not allp:
        log("no parts match --only")
        return 1
    total = sum(p["size"] for p in allp)
    missing = sum(p["size"] for p in allp if not verified(zips / p["key"], p["size"], p["checksum"]))
    largest = max(p["size"] for p in allp)
    need = missing + largest * 1.3 * a.workers + 2 * GB  # zips still to fetch + unpacked videos being processed + output
    free = shutil.disk_usage(a.root).free
    log(f"{len(allp)} parts, {total / GB:.1f} GB in total, {missing / GB:.1f} GB still to download; "
        f"free on this drive {free / GB:.1f} GB, needed about {need / GB:.1f} GB")
    if free < need:
        log("ERROR  not enough free space. Free some space, use --only for a subset, or --workers 1.")
        return 1

    # 1. download sequentially (polite to Zenodo); resumable per part
    for i, p in enumerate(allp, 1):
        log(f"download {i}/{len(allp)} {p['key']} ({p['size'] / GB:.2f} GB) ...")
        log(f"  {fetch_part(p, zips)}")
    log(f"all {len(allp)} zips present and checksum-verified in {zips}")
    if a.download_only:
        return 0

    # 2. MediaPipe task files
    for name, url in TASKS.items():
        if name == "face_landmarker.task" and a.no_face:
            continue
        dest = tasks / name
        if not dest.exists():
            log(f"downloading {name} ...")
            req = urllib.request.Request(url, headers={"User-Agent": "isl-nova-include-local"})  # noqa: S310 - fixed https URL
            with urllib.request.urlopen(req, timeout=300) as r, dest.open("wb") as fh:  # noqa: S310
                shutil.copyfileobj(r, fh)

    # 3. extract in parallel
    log(f"extracting landmarks with {a.workers} worker(s), face={'off' if a.no_face else 'on'} "
        f"(this is the long step: expect several hours for all parts on a laptop CPU)")
    failed = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(extract_part, p, zips, parts, work, tasks, not a.no_face, a.max_side): p for p in allp}
        for n, fut in enumerate(as_completed(futs), 1):
            p = futs[fut]
            try:
                log(f"extract {n}/{len(allp)} {p['key']}: {fut.result()}")
                if a.delete_zips:
                    (zips / p["key"]).unlink(missing_ok=True)
            except Exception as exc:  # noqa: BLE001 - reported, others continue
                failed.append(p["key"])
                log(f"extract {n}/{len(allp)} {p['key']}: FAILED {exc}")
    log(f"extraction finished in {(time.time() - t0) / 3600:.2f} h")
    if failed:
        log(f"ERROR  {len(failed)} part(s) failed: {failed}. Rerun the same command to retry only those.")
        return 1

    # 4. merge
    log(f"merging into {merged} ...")
    shutil.rmtree(merged, ignore_errors=True)
    rc = subprocess.run([sys.executable, "-m", "isl_nova_ml.include_pipeline", "merge", "--inputs", str(parts),  # noqa: S603
                         "--out", str(merged), "--version", a.version], cwd=ROOT,
                        env={**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "ml"), str(ROOT / "backend")])}).returncode
    if rc != 0:
        log("ERROR  merge failed (see above)")
        return 1
    if not a.no_face:  # merge writes the 1.0.0 label; the files carry face points, so record the richer contract
        m = json.loads((merged / "manifest.json").read_text())
        m["feature_contract"] = "isl-nova-fc-2.0.0"
        (merged / "manifest.json").write_text(json.dumps(m, indent=1))
    shutil.copytree(ROOT / "dataset" / "sources" / "include", merged / "attribution", dirs_exist_ok=True)
    log("done. Train with:")
    model = "bilstm-attn-face" if not a.no_face else "bilstm-attn"
    log(f"  python scripts/train_local.py --data {merged} --model {model} --promote")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
