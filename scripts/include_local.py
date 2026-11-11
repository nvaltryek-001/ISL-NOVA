"""Download the full INCLUDE video dataset and extract landmarks on your own computer.

    python scripts/include_local.py                    # everything: download, extract (hands, pose, face), merge
    python scripts/include_local.py --download-only    # only fetch and verify the 56.8 GB of zips
    python scripts/include_local.py --workers 4        # more parallel extraction processes (CPU cores)
    python scripts/include_local.py --only Adjectives  # a subset (zip names or category prefixes)
    python scripts/include_local.py --delete-zips      # low disk: download, extract, delete one part at a time (~15 GB)

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
import urllib.error
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


def download_resumable(url: str, tmp: Path, size: int, checksum: str, attempts: int = 40) -> dict:
    """Download into tmp, continuing from its current size with an HTTP Range request after any
    dropped connection (also across runs: an interrupted .partial file is picked up next time).
    The whole file is checked against Zenodo's MD5 at the end; a mismatch restarts from zero."""
    from isl_nova_ml.include_pipeline import UA, _https

    algo, _, want = checksum.partition(":")
    t0, start_bytes = time.time(), (tmp.stat().st_size if tmp.exists() else 0)
    for attempt in range(1, attempts + 1):
        have = tmp.stat().st_size if tmp.exists() else 0
        if have > size:
            tmp.unlink()
            have = 0
        if have < size:
            headers = {"User-Agent": UA}
            if have:
                headers["Range"] = f"bytes={have}-"
            try:
                req = urllib.request.Request(_https(url), headers=headers)  # noqa: S310 - https enforced by _https
                with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310
                    mode = "ab" if have and r.status == 206 else "wb"  # 200 = server ignored Range: start over
                    if mode == "wb" and have:
                        log("  server does not support resume; restarting this part")
                    with tmp.open(mode) as out:
                        last = time.time()
                        while chunk := r.read(1 << 22):
                            out.write(chunk)
                            if time.time() - last > 30:
                                done = out.tell()
                                log(f"  {done / GB:.2f} / {size / GB:.2f} GB")
                                last = time.time()
            except (OSError, urllib.error.URLError) as exc:  # dropped connection, timeout, reset ...
                wait = min(60, 5 * attempt)
                got = tmp.stat().st_size if tmp.exists() else 0
                log(f"  connection problem ({exc}); have {got / GB:.2f} GB, resuming in {wait} s "
                    f"(attempt {attempt}/{attempts})")
                time.sleep(wait)
                continue
        if tmp.stat().st_size == size:
            got = file_hash(tmp, algo or "md5")
            if not want or got == want:
                secs = max(time.time() - t0, 1e-3)
                return {"bytes": size, "mb_per_s": round((size - start_bytes) / 1e6 / secs, 2)}
            log(f"  checksum mismatch ({got} != {want}); downloading this part again")
            tmp.unlink()
    raise RuntimeError(f"gave up after {attempts} attempts; rerun the same command to continue")


def fetch_part(meta: dict, zips: Path) -> str:
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
    if tmp.exists():
        log(f"  continuing an interrupted download ({tmp.stat().st_size / GB:.2f} GB already here)")
    r = download_resumable(meta["url"], tmp, meta["size"], meta["checksum"])
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
    done = [p for p in allp if (parts / p["key"].replace(" ", "_") / "part_manifest.json").exists()]
    todo = [p for p in allp if p not in done]
    have = [p for p in todo if verified(zips / p["key"], p["size"], p["checksum"])]
    missing = sum(p["size"] for p in todo if p not in have)
    largest = max(p["size"] for p in allp)
    streaming = a.delete_zips and not a.download_only
    if streaming:  # at most workers+1 zips (plus their unpacked videos) on disk at any time
        need = largest * 2.3 * (a.workers + 1) + 3 * GB
    else:
        need = missing + largest * 1.3 * a.workers + 2 * GB
    free = shutil.disk_usage(a.root).free
    log(f"{len(allp)} parts ({total / GB:.1f} GB): {len(done)} already extracted, {len(have)} downloaded and waiting, "
        f"{len(todo) - len(have)} still to download ({missing / GB:.1f} GB)")
    log(f"free on this drive {free / GB:.1f} GB, needed about {need / GB:.1f} GB"
        + ("  [--delete-zips: each zip is removed right after its landmarks are extracted]" if streaming else ""))
    if free < need:
        log("ERROR  not enough free space. Use --delete-zips, fewer --workers, or --only for a subset.")
        return 1

    # MediaPipe task files
    if not a.download_only:
        for name, url in TASKS.items():
            if name == "face_landmarker.task" and a.no_face:
                continue
            dest = tasks / name
            if not dest.exists():
                log(f"downloading {name} ...")
                req = urllib.request.Request(url, headers={"User-Agent": "isl-nova-include-local"})  # noqa: S310 - fixed https URL
                with urllib.request.urlopen(req, timeout=300) as r, dest.open("wb") as fh:  # noqa: S310
                    shutil.copyfileobj(r, fh)

    failed: list[str] = []
    t0 = time.time()
    counter = {"n": len(done)}

    def finish(fut, p):
        try:
            log(f"extract {counter['n'] + 1}/{len(allp)} {p['key']}: {fut.result()}")
            if a.delete_zips:
                (zips / p["key"]).unlink(missing_ok=True)
                (zips / (p["key"] + ".ok")).unlink(missing_ok=True)
        except Exception as exc:  # noqa: BLE001 - reported, others continue
            failed.append(p["key"])
            log(f"extract {counter['n'] + 1}/{len(allp)} {p['key']}: FAILED {exc}")
        counter["n"] += 1

    if streaming:
        # download one part, hand it to an extraction worker, download the next; delete each zip when done
        import threading
        slots = threading.BoundedSemaphore(a.workers + 1)
        log(f"download + extract part by part with {a.workers} worker(s), face={'off' if a.no_face else 'on'} "
            f"(the long step: expect many hours for all parts on a laptop)")
        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            futs = []
            for i, p in enumerate(todo, 1):
                slots.acquire()
                try:
                    log(f"download {len(done) + i}/{len(allp)} {p['key']} ({p['size'] / GB:.2f} GB) ...")
                    log(f"  {fetch_part(p, zips)}")
                except Exception as exc:  # noqa: BLE001
                    slots.release()
                    failed.append(p["key"])
                    log(f"  download FAILED {exc}; rerun later to retry this part")
                    continue
                fut = pool.submit(extract_part, p, zips, parts, work, tasks, not a.no_face, a.max_side)
                fut.add_done_callback(lambda f, p=p: (finish(f, p), slots.release()))
                futs.append(fut)
            for f in futs:
                f.exception()  # wait
    else:
        # 1. download sequentially (polite to Zenodo); resumable per part
        for i, p in enumerate(todo, 1):
            log(f"download {i}/{len(todo)} {p['key']} ({p['size'] / GB:.2f} GB) ...")
            log(f"  {fetch_part(p, zips)}")
        log(f"all {len(todo)} remaining zips present and checksum-verified in {zips}")
        if a.download_only:
            return 0
        log(f"extracting landmarks with {a.workers} worker(s), face={'off' if a.no_face else 'on'} "
            f"(the long step: expect several hours for all parts on a laptop CPU)")
        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            futs = {pool.submit(extract_part, p, zips, parts, work, tasks, not a.no_face, a.max_side): p for p in todo}
            for fut in as_completed(futs):
                finish(fut, futs[fut])
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
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nstopped. Rerun the same command to continue where it left off.")
        raise SystemExit(130) from None
