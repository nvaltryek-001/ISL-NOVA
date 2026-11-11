"""Staged INCLUDE pipeline used by .github/workflows/include-*.yml.

    python -m isl_nova_ml.include_pipeline preflight --out preflight.json
    python -m isl_nova_ml.include_pipeline parts            # JSON list for a job matrix
    python -m isl_nova_ml.include_pipeline extract-part --part Greetings_1of2.zip --out out/
    python -m isl_nova_ml.include_pipeline merge --inputs parts/ --out merged/
    python -m isl_nova_ml.include_pipeline compare --registry reg/ --out report/

INCLUDE (Sridhar et al., ACM MM 2020, doi:10.1145/3394171.3413528) is CC BY 4.0.
Raw videos are downloaded to the runner, processed and deleted; only
landmark files and manifests leave the job.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
import sys
import time
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ZENODO_RECORD = "4010759"
ZENODO_API = f"https://zenodo.org/api/records/{ZENODO_RECORD}"
REPO = Path(__file__).resolve().parents[2]
SPLITS = REPO / "dataset" / "sources" / "include"
VOCAB = REPO / "dataset" / "vocabulary" / "signs_master.csv"
VIDEO_EXT = {".mov", ".mp4", ".avi", ".mkv", ".m4v"}
UA = "isl-nova-pipeline/0.1 (+https://github.com/nvaltryek-001/ISL-NOVA)"


def norm(folder: str) -> str:
    """INCLUDE's own label normalisation: letters only, lower case."""
    return "".join(ch for ch in folder if ch.isalpha()).lower()


def _https(url: str) -> str:
    if not url.startswith("https://"):
        raise ValueError(f"refusing non-https URL {url!r}")
    return url


def http_json(url: str) -> dict:
    req = urllib.request.Request(_https(url), headers={"User-Agent": UA, "Accept": "application/json"})  # noqa: S310
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 - fixed https URLs
        return json.loads(r.read())


def zenodo_files() -> tuple[dict, list[dict]]:
    rec = http_json(ZENODO_API)
    files = []
    for f in rec.get("files", []):
        files.append({"key": f["key"], "size": f["size"], "checksum": f.get("checksum", ""),
                      "url": f.get("links", {}).get("self") or
                      f"https://zenodo.org/records/{ZENODO_RECORD}/files/{f['key']}?download=1"})
    return rec, sorted(files, key=lambda x: x["key"])


def split_index() -> dict[tuple[str, str], tuple[str, str]]:
    """(gloss, filename lower) -> (split, original relative path)."""
    idx = {}
    for split in ("train", "val", "test"):
        for line in (SPLITS / f"include_{split}.txt").read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            _cat, folder, fname = line.split("/", 2)
            idx[(norm(folder), fname.lower())] = (split, line)
            idx.setdefault((norm(folder), "stem:" + Path(fname).stem.lower()), (split, line))
    return idx


def vocab() -> dict[str, str]:
    with VOCAB.open(newline="", encoding="utf-8") as fh:
        return {r["source_gloss"]: r["sign_id"] for r in csv.DictReader(fh)}


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path, checksum: str, retries: int = 6) -> dict:
    algo, _, want = checksum.partition(":")
    for attempt in range(1, retries + 1):
        try:
            t0 = time.time()
            h = hashlib.new(algo or "md5")
            req = urllib.request.Request(_https(url), headers={"User-Agent": UA})  # noqa: S310
            with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as out:  # noqa: S310
                while chunk := r.read(1 << 22):
                    h.update(chunk)
                    out.write(chunk)
            got = h.hexdigest()
            if want and got != want:
                raise OSError(f"checksum mismatch {got} != {want}")
            secs = time.time() - t0
            return {"bytes": dest.stat().st_size, "seconds": round(secs, 1), "attempts": attempt,
                    "checksum_verified": bool(want), "checksum": f"{algo}:{got}",
                    "mb_per_s": round(dest.stat().st_size / 1e6 / max(secs, 1e-3), 2)}
        except Exception as exc:  # noqa: BLE001 - retried, then re-raised
            print(f"download attempt {attempt} failed: {exc}", flush=True)
            if attempt == retries:
                raise
            time.sleep(min(300, 15 * 2 ** attempt))
    raise RuntimeError("unreachable")


# --------------------------------------------------------------------------- stages

def cmd_preflight(a) -> int:
    rep: dict = {"python": sys.version.split()[0], "platform": platform.platform(), "cpus": os.cpu_count()}
    du = shutil.disk_usage("/")
    rep["disk_free_gb"] = round(du.free / 1e9, 1)
    try:
        mem = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
        rep["mem_total_gb"] = round(int(mem["MemTotal"].split()[0]) / 1e6, 1)
    except (OSError, KeyError, ValueError):
        rep["mem_total_gb"] = None
    rec, files = zenodo_files()
    md = rec.get("metadata", {})
    lic = md.get("license") or {}
    rep["zenodo"] = {"record": ZENODO_RECORD, "title": md.get("title"), "doi": md.get("doi") or rec.get("doi"),
                     "license": lic.get("id") if isinstance(lic, dict) else lic,
                     "files": len(files), "total_gb": round(sum(f["size"] for f in files) / 1e9, 2),
                     "zip_parts": [f["key"] for f in files if f["key"].endswith(".zip")]}
    idx = split_index()
    voc = vocab()
    glosses = {g for g, _ in idx}
    mapped = set(voc) & glosses
    per = Counter()
    for (g, _), (split, _) in idx.items():
        if g in voc:
            per[(voc[g], split)] += 1
    rep["vocabulary"] = {"slots": len(voc), "slots_with_split_entries": len(mapped),
                         "missing": sorted(set(voc) - glosses),
                         "videos_listed_for_slots": sum(per.values()),
                         "by_split": dict(Counter(s for (_, s) in per.elements()))}
    biggest = max((f["size"] for f in files), default=0)
    rep["estimate"] = {"largest_part_gb": round(biggest / 1e9, 2),
                       "needed_per_job_gb": round(biggest * 2.2 / 1e9, 1),
                       "fits_runner_disk": rep["disk_free_gb"] > biggest * 2.2 / 1e9}
    Path(a.out).write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep, indent=2))
    return 0


def cmd_parts(a) -> int:
    _, files = zenodo_files()
    parts = [f for f in files if f["key"].endswith(".zip")]
    if a.only:
        want = set(a.only.split(","))
        parts = [p for p in parts if p["key"] in want or p["key"].split("_")[0] in want]
    print(json.dumps([p["key"] for p in parts]))
    return 0


def cmd_extract_part(a) -> int:
    from .data import save_landmarks
    from .extract import LandmarkExtractor
    from .features import extract_features

    out = Path(a.out)
    (out / "landmarks").mkdir(parents=True, exist_ok=True)
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    _, files = zenodo_files()
    meta = next(f for f in files if f["key"] == a.part)
    local_zip = getattr(a, "zip", None)
    zpath = Path(local_zip) if local_zip else work / a.part
    report: dict = {"part": a.part, "zenodo_size": meta["size"], "zenodo_checksum": meta["checksum"]}
    if local_zip:  # already downloaded and checksum-verified by the caller (scripts/include_local.py); kept
        report["download"] = {"local_zip": str(zpath), "bytes": zpath.stat().st_size}
    else:
        report["download"] = download(meta["url"], zpath, meta["checksum"])
    t0 = time.time()
    with zipfile.ZipFile(zpath) as z:
        bad = z.testzip()
        if bad:
            report["zip_corrupt_member"] = bad
        names = [n for n in z.namelist() if Path(n).suffix.lower() in VIDEO_EXT]
        report["videos_in_zip"] = len(names)
        report["zip_layout_example"] = names[:3]
        z.extractall(work / "x")
    if not local_zip:
        zpath.unlink()
    idx, voc = split_index(), vocab()
    ex = LandmarkExtractor(Path(a.hand_model), Path(a.pose_model), max_side=a.max_side,
                           face_model=Path(a.face_model) if getattr(a, "face_model", None) else None)
    entries, reserve, failures, unmatched, outside_vocab = [], [], [], [], 0
    duplicates: list[dict] = []
    seen_listed: dict[str, str] = {}
    try:
        for n in sorted(names):
            p = work / "x" / n
            gloss = norm(p.parent.name)
            hit = idx.get((gloss, p.name.lower())) or idx.get((gloss, "stem:" + p.stem.lower()))
            if hit is None:
                unmatched.append(n)
                continue
            open_set = gloss not in voc
            if open_set and not a.include_reserve:
                outside_vocab += 1
                continue
            split, listed = hit
            rid = f"include:{gloss}:{p.stem}"
            if listed in seen_listed:  # two files resolve to one official split entry
                duplicates.append({"path": n, "split_entry": listed, "kept": seen_listed[listed]})
                continue
            seen_listed[listed] = n
            try:
                frames, aspect, vmeta = ex.video(p)
            except Exception as exc:  # noqa: BLE001 - recorded per video
                failures.append({"recording_id": rid, "path": n, "reason": str(exc)[:300]})
                continue
            if ex.face is not None:
                vmeta["face_frame_ratio"] = round(sum(f.get("face") is not None for f in frames) / max(len(frames), 1), 3)
            rel = f"landmarks/{gloss}__{p.stem}.npz"
            sha = save_landmarks(out / rel, frames, aspect)
            q = extract_features(frames, aspect)
            (reserve if open_set else entries).append({"recording_id": rid, "sign_id": f"RESERVE:{gloss}" if open_set else voc[gloss], "gloss": gloss, "split": split,
                            "open_set": open_set,
                            "signer_id": "unknown:include", "session_id": "unknown:include",
                            "landmarks_path": rel, "sha256": sha, "video_sha256": sha256_file(p),
                            "source": "include", "license": "CC BY 4.0", "approved": True,
                            "source_path": listed, "quality": {"status": q.status, "reasons": q.reasons,
                                                               "hand_frame_ratio": round(q.hand_frame_ratio, 3),
                                                               "pose_frame_ratio": round(q.pose_frame_ratio, 3),
                                                               **vmeta}})
            if (len(entries) + len(reserve)) % 25 == 0 or len(entries) + len(reserve) == 1:
                print(f"{a.part}: {len(entries)} videos processed; last: {len(frames)} frames, "
                      f"face frames {sum(f.get('face') is not None for f in frames)}, face task={ex.face is not None}",
                      flush=True)
    finally:
        ex.close()
        shutil.rmtree(work / "x", ignore_errors=True)
    report.update({"processed": len(entries), "reserve_processed": len(reserve), "failed": len(failures), "unmatched_to_split_lists": len(unmatched),
                   "outside_isl_nova_vocabulary": outside_vocab,
                   "duplicate_files_for_one_split_entry": duplicates, "extract_seconds": round(time.time() - t0, 1),
                   "insufficient_input": sum(e["quality"]["status"] != "ok" for e in entries)})
    (out / "part_manifest.json").write_text(json.dumps({"report": report, "entries": entries, "open_set_entries": reserve, "failures": failures,
                                                        "unmatched": unmatched}, indent=1))
    print(json.dumps(report, indent=2))
    if unmatched:
        print("UNMATCHED (not in official split lists):", json.dumps(unmatched[:60]))
        listed = sorted(v[1] for k, v in idx.items() if not k[1].startswith("stem:") and v[1].startswith(a.part.rsplit("_", 1)[0] + "/"))
        print("LISTED FOR THIS CATEGORY (sample):", json.dumps(listed[:60]))
    return 0


def cmd_merge(a) -> int:
    inp, out = Path(a.inputs), Path(a.out)
    (out / "landmarks").mkdir(parents=True, exist_ok=True)
    entries, open_set, failures, reports = [], [], [], []
    for m in sorted(inp.glob("**/part_manifest.json")):
        d = json.loads(m.read_text())
        reports.append(d["report"])
        failures += d["failures"]
        for key, bucket in (("entries", entries), ("open_set_entries", open_set)):
            for e in d.get(key, []):
                shutil.copy2(m.parent / e["landmarks_path"], out / e["landmarks_path"])
                bucket.append(e)
    ids = Counter(e["recording_id"] for e in entries + open_set)
    dups = [k for k, c in ids.items() if c > 1]
    per_class = defaultdict(Counter)
    for e in entries:
        per_class[e["sign_id"]][e["split"]] += 1
        if e["quality"]["status"] != "ok":
            per_class[e["sign_id"]]["insufficient_input"] += 1
    with VOCAB.open(newline="", encoding="utf-8") as fh:
        all_slots = [r["sign_id"] for r in csv.DictReader(fh)]
    summary = {
        "parts_processed": len(reports), "videos_downloaded_in_parts": sum(r.get("videos_in_zip", 0) for r in reports),
        "bytes_downloaded": sum(r["download"]["bytes"] for r in reports),
        "usable_landmark_sequences": len(entries), "failed_videos": len(failures),
        "insufficient_input_sequences": sum(e["quality"]["status"] != "ok" for e in entries),
        "duplicate_recording_ids": dups, "by_split": dict(Counter(e["split"] for e in entries)),
        "classes_with_data": len(per_class), "slots_without_data": sorted(set(all_slots) - set(per_class)),
        "classes_with_train_val_test": sum(1 for c in per_class.values() if c["train"] and c["val"] and c["test"]),
        "open_set_sequences": len(open_set), "open_set_classes": len({e["gloss"] for e in open_set}),
        "signer_ids": "not provided by INCLUDE; signer independence cannot be verified",
    }
    manifest = {"dataset_version": a.version, "source": "INCLUDE (doi:10.1145/3394171.3413528), CC BY 4.0",
                "feature_contract": "isl-nova-fc-1.0.0", "split_policy": "INCLUDE official train/val/test lists",
                "summary": summary, "entries": entries,
                "open_set_entries": open_set, "open_set_note": "INCLUDE reserve glosses outside the 200-class vocabulary; never used for training"}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    (out / "failures.json").write_text(json.dumps(failures, indent=1))
    (out / "part_reports.json").write_text(json.dumps(reports, indent=1))
    with (out / "per_class_counts.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["sign_id", "train", "val", "test", "insufficient_input"])
        for sid in all_slots:
            c = per_class.get(sid, Counter())
            w.writerow([sid, c["train"], c["val"], c["test"], c["insufficient_input"]])
    print(json.dumps(summary, indent=2))
    return 0 if not dups else 1


def cmd_compare(a) -> int:
    from .registry import Registry

    root = Path(a.registry)
    reg = Registry(root)
    rows = []
    for d in sorted(p for p in root.iterdir() if (p / "model.json").exists()):
        info = json.loads((d / "model.json").read_text())
        m = json.loads((d / "metrics.json").read_text())
        if not any(x["model_id"] == info["model_id"] for x in reg.read()["models"]):
            reg.register(d)
        t, v = m["test"], m["validation"]
        prec = [c["precision"] for c in t["per_class"] if c["support"] > 0]
        rec = [c["recall"] for c in t["per_class"] if c["support"] > 0]
        rows.append({"model_id": info["model_id"], "kind": info["kind"], "classes": len(info["classes"]),
                     "train": info["lineage"]["split_counts"]["train"], "val": info["lineage"]["split_counts"]["val"],
                     "test": t["n"], "val_macro_f1": v["macro_f1"], "test_top1": t["top1"], "test_top5": t["top5"],
                     "test_macro_precision": sum(prec) / len(prec), "test_macro_recall": sum(rec) / len(rec),
                     "test_macro_f1": t["macro_f1"], "test_weighted_f1": t["weighted_f1"], "test_ece": t["ece"],
                     "latency_ms": m["latency_ms_per_sample_batch"], "size_bytes": m["model_size_bytes"],
                     "train_seconds": info.get("train_seconds"), "synthetic": info["synthetic"]})
    if not rows:
        print("no models found")
        return 1
    # selection on VALIDATION; exact ties go to the smaller model (cheaper, runs on-device)
    best = max((r for r in rows if not r["synthetic"]), key=lambda r: (r["val_macro_f1"], -r["size_bytes"]))
    reg.promote(best["model_id"], actor="include-train workflow")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "comparison.json").write_text(json.dumps({"selected_by": "validation macro-F1 (ties: smaller model)", "best": best["model_id"],
                                                     "models": rows}, indent=2))
    pct = lambda x: f"{100 * x:.1f}%"  # noqa: E731
    lines = ["| Model | Classes | Train/Val/Test | Val macro-F1 | Test top-1 | Test top-5 | Precision (macro) | "
             "Recall (macro) | Macro-F1 | Weighted-F1 | ECE | Latency ms | Size |",
             "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in sorted(rows, key=lambda r: -r["val_macro_f1"]):
        mark = " **(selected)**" if r is best else ""
        lines.append(f"| {r['kind']}{mark} | {r['classes']} | {r['train']}/{r['val']}/{r['test']} | {pct(r['val_macro_f1'])} | "
                     f"{pct(r['test_top1'])} | {pct(r['test_top5'])} | {pct(r['test_macro_precision'])} | "
                     f"{pct(r['test_macro_recall'])} | {pct(r['test_macro_f1'])} | {pct(r['test_weighted_f1'])} | "
                     f"{r['test_ece']:.3f} | {r['latency_ms']:.2f} | {r['size_bytes'] / 1e6:.2f} MB |")
    (out / "comparison.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg  # bundled with imageio-ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def cmd_fetch_test_videos(a) -> int:
    """Prepare held-out test-split videos as Y4M files for a browser virtual camera,
    plus the offline (Python MediaPipe) prediction for the same videos."""
    import subprocess

    from .extract import LandmarkExtractor
    from .inference import Predictor

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    _, files = zenodo_files()
    meta = {f["key"]: f for f in files}
    idx, voc = split_index(), vocab()
    pred = Predictor.from_registry(Path(a.registry))
    ex = LandmarkExtractor(Path(a.hand_model), Path(a.pose_model),
                           face_model=Path(a.face_model) if getattr(a, "face_model", None) else None)
    items = []
    try:
        for part in [x for x in a.parts.split(",") if x]:
            z = work / part
            download(meta[part]["url"], z, meta[part]["checksum"])
            with zipfile.ZipFile(z) as zf:
                names = [n for n in zf.namelist() if Path(n).suffix.lower() in VIDEO_EXT]
                for n in names:
                    p = Path(n)
                    gloss = norm(p.parent.name)
                    hit = idx.get((gloss, p.name.lower())) or idx.get((gloss, "stem:" + p.stem.lower()))
                    if not hit or hit[0] != "test" or gloss not in voc:
                        continue
                    src = work / "v" / p.name
                    src.parent.mkdir(exist_ok=True)
                    src.write_bytes(zf.read(n))
                    vid = f"{gloss}__{p.stem}"
                    y4m = out / f"{vid}.y4m"
                    cmd = [_ffmpeg(), "-loglevel", "error", "-y", "-i", str(src), "-vf", "scale=640:-2,fps=25",
                           "-pix_fmt", "yuv420p", str(y4m)]
                    subprocess.run(cmd, check=True)  # noqa: S603 - fixed binary, paths we created
                    frames, aspect, vmeta = ex.video(src)
                    off = pred.predict(frames, aspect, 5)
                    items.append({"id": vid, "sign_id": voc[gloss], "gloss": gloss, "y4m": y4m.name,
                                  "duration_s": round(vmeta["frames"] / vmeta["fps"], 2),
                                  "offline": {"state": off["state"], "top1": off["top"][0]["sign_id"] if off["top"] else None,
                                              "p": off["top"][0]["probability"] if off["top"] else None}})
                    src.unlink()
                    if a.limit and len(items) >= a.limit:
                        break
            z.unlink()
            if a.limit and len(items) >= a.limit:
                break
    finally:
        ex.close()
    (out / "videos.json").write_text(json.dumps({"model_id": pred.info["model_id"], "videos": items}, indent=2))
    ok = sum(i["offline"]["top1"] == i["sign_id"] for i in items)
    print(json.dumps({"videos": len(items), "offline_top1_correct": ok}, indent=2))
    return 0


def cmd_verify(a) -> int:
    """Load the promoted model exactly as the API does and re-run the test split."""
    import numpy as np

    from .data import load_landmarks
    from .inference import Predictor

    pred = Predictor.from_registry(Path(a.registry))
    known = {c["sign_id"] for c in pred.vocabulary}
    entries = [e for e in json.loads(Path(a.manifest).read_text())["entries"] if e["split"] == "test" and e["sign_id"] in known]
    states, correct, top5, lat = Counter(), 0, 0, []
    for e in entries:
        frames, aspect = load_landmarks(Path(a.data_root) / e["landmarks_path"])
        t0 = time.perf_counter()
        out = pred.predict(frames, aspect, 5)
        lat.append((time.perf_counter() - t0) * 1000)
        states[out["state"]] += 1
        ids = [t["sign_id"] for t in out["top"]]
        correct += bool(ids) and ids[0] == e["sign_id"]
        top5 += e["sign_id"] in ids
    n = len(entries)
    rep = {"model_id": pred.info["model_id"], "kind": pred.info["kind"], "loaded_via": "isl_nova_ml.inference.Predictor",
           "test_sequences": n, "top1_end_to_end": correct / n if n else None, "top5_end_to_end": top5 / n if n else None,
           "states": dict(states), "latency_ms_median": float(np.median(lat)) if lat else None,
           "latency_ms_p95": float(np.percentile(lat, 95)) if lat else None,
           "note": "end-to-end = landmark file -> feature contract -> calibrated model -> state; includes insufficient-input sequences"}
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "verify.json").write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep, indent=2))
    return 0


def cmd_open_set(a) -> int:
    """Unknown-sign detection: known held-out test signs vs INCLUDE reserve glosses never seen in training."""
    import numpy as np

    from .data import load_landmarks
    from .inference import Predictor
    from .metrics import auroc

    pred = Predictor.from_registry(Path(a.registry))
    known_ids = {c["sign_id"] for c in pred.vocabulary}
    man = json.loads(Path(a.manifest).read_text())
    groups = {"known": [e for e in man["entries"] if e["split"] == "test" and e["sign_id"] in known_ids],
              "unknown": [e for e in man.get("open_set_entries", []) if e.get("open_set")]}
    rows, scores = [], {"known": [], "unknown": []}
    for g, ents in groups.items():
        for e in ents:
            frames, aspect = load_landmarks(Path(a.data_root) / e["landmarks_path"])
            fr = pred.features(frames, aspect)
            out = pred.predict(frames, aspect, 5)
            p1 = pred.known_max(pred.predict_features(fr.features)) if fr.status == "ok" else None
            if p1 is not None:
                scores[g].append(p1)
            top = out["top"][0]["sign_id"] if out["top"] else None
            rows.append({"group": g, "gloss": e.get("gloss"), "sign_id": e["sign_id"], "state": out["state"],
                         "top1": top, "max_prob": p1, "correct": g == "known" and top == e["sign_id"]})
    k, u = np.array(scores["known"]), np.array(scores["unknown"])

    def states(g):
        return dict(Counter(r["state"] for r in rows if r["group"] == g))

    sweep = []
    for t in np.round(np.arange(0.1, 0.96, 0.05), 2):
        sweep.append({"threshold": float(t), "known_accept_rate": float((k >= t).mean()) if k.size else None,
                      "unknown_reject_rate": float((u < t).mean()) if u.size else None})
    fpr95 = None
    if k.size and u.size:
        t95 = float(np.percentile(k, 5))  # threshold keeping 95% of known sequences
        fpr95 = {"threshold": t95, "unknown_accept_rate": float((u >= t95).mean())}
    kn = [r for r in rows if r["group"] == "known"]
    un = [r for r in rows if r["group"] == "unknown"]
    rep = {
        "model_id": pred.info["model_id"], "tau": pred.tau, "margin": pred.margin,
        "known_test_sequences": len(kn), "unknown_sequences": len(un),
        "unknown_glosses": len({r["gloss"] for r in un}),
        "scored_known": int(k.size), "scored_unknown": int(u.size),
        "auroc_maxprob_known_vs_unknown": auroc(k, u) if k.size and u.size else None,
        "known_states": states("known"), "unknown_states": states("unknown"),
        "unknown_false_recognition_rate": (sum(r["state"] == "recognized" for r in un) / len(un)) if un else None,
        "unknown_rejected_rate_unknown_or_uncertain": (sum(r["state"] in ("unknown", "uncertain") for r in un) / len(un)) if un else None,
        "known_recognized_and_correct_rate": (sum(r["state"] == "recognized" and r["correct"] for r in kn) / len(kn)) if kn else None,
        "known_recognized_but_wrong_rate": (sum(r["state"] == "recognized" and not r["correct"] for r in kn) / len(kn)) if kn else None,
        "unknown_accept_at_95pct_known_accept": fpr95, "threshold_sweep": sweep,
        "protocol": "Known = INCLUDE official test split of the 200 trained classes. Unknown = INCLUDE glosses outside "
                    "the vocabulary (reserve), never used in training, calibration or threshold selection. Same signers "
                    "and recording conditions as training; this is not an evaluation on unseen signers.",
    }
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "open_set.json").write_text(json.dumps(rep, indent=2))
    with (Path(a.out) / "open_set_rows.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["group"])
        w.writeheader()
        w.writerows(rows)
    print(json.dumps({x: v for x, v in rep.items() if x != "threshold_sweep"}, indent=2))
    return 0


def cmd_open_set_v2(a) -> int:
    """Compare unknown-sign detectors with disjoint unknown glosses for tuning and evaluation."""
    import numpy as np

    from .data import load_landmarks
    from .inference import Predictor
    from .openset import CentroidScorer, base_scores, evaluate, gloss_half, pooled, unknown_part

    pred = Predictor.from_registry(Path(a.registry))
    known_ids = {c["sign_id"] for c in pred.vocabulary}
    cidx = {c["sign_id"]: i for i, c in enumerate(pred.vocabulary)}
    man = json.loads(Path(a.manifest).read_text())

    def feats(entries):
        P, Z, keep = [], [], []
        for e in entries:
            frames, aspect = load_landmarks(Path(a.data_root) / e["landmarks_path"])
            fr = pred.features(frames, aspect)
            if fr.status != "ok":
                continue
            F = np.asarray(fr.features, dtype=np.float64)
            P.append(pred.predict_features(F)[pred.known_cols])
            Z.append(pooled(F))
            keep.append(e)
        return np.array(P), np.array(Z), keep

    by = {sp: [e for e in man["entries"] if e["split"] == sp and e["sign_id"] in known_ids] for sp in ("train", "val", "test")}
    unk = [e for e in man.get("open_set_entries", []) if e.get("open_set")]
    # an "__other__" model was trained on part A1, so only part A2 may fit detectors for it
    halves = {"A": [e for e in unk if (unknown_part(e["gloss"]) == "A2" if pred.other_col is not None
                                        else gloss_half(e["gloss"]) == "A")],
              "B": [e for e in unk if gloss_half(e["gloss"]) == "B"]}
    _, Ztr, ktr = feats(by["train"])
    cent = CentroidScorer().fit(Ztr, np.array([cidx[e["sign_id"]] for e in ktr]))
    parts = {}
    for name, ents in (("val", by["val"]), ("test", by["test"]), ("unkA", halves["A"]), ("unkB", halves["B"])):
        P, Z, _ = feats(ents)
        parts[name] = base_scores(P, cent.score(Z))
    rep = evaluate({"known": parts["val"], "unknown": parts["unkA"]}, {"known": parts["test"], "unknown": parts["unkB"]})
    out = {"model_id": pred.info["model_id"],
           "protocol": "fit: known validation + unknown glosses half A; eval: known test + unknown glosses half B "
                       "(disjoint glosses); thresholds chosen on the fit set only",
           "counts": {"train_for_centroids": len(ktr), "val_known": len(parts["val"]["maxprob"]),
                      "test_known": len(parts["test"]["maxprob"]), "unknown_A": len(parts["unkA"]["maxprob"]),
                      "unknown_B": len(parts["unkB"]["maxprob"]),
                      "glosses_A": len({e["gloss"] for e in halves["A"]}), "glosses_B": len({e["gloss"] for e in halves["B"]})},
           "detectors": rep}
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "open_set_v2.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=1))
    return 0


def _entries_and_parts(a, pred):
    from .data import assign_splits, training_eligible
    from .openset import unknown_part

    man = json.loads(Path(a.manifest).read_text())
    known_ids = {c["sign_id"] for c in pred.vocabulary}
    seed = int((pred.info.get("config") or {}).get("seed", 13))
    if pred.info["kind"] == "ensemble":
        seed = int(json.loads((pred.dir / "architecture.json").read_text())["members"][0].get("seed", 13))
    entries = assign_splits([e for e in man["entries"] if training_eligible(e)[0]], seed=seed)  # as in training
    by = {sp: [e for e in entries if e["split"] == sp and e["sign_id"] in known_ids] for sp in ("val", "test")}
    unk = [e for e in man.get("open_set_entries", []) if e.get("open_set")]
    parts = {k: [e for e in unk if unknown_part(e["gloss"]) == k] for k in ("A1", "A2", "B")}
    return by, parts


def _probs(a, pred, entries):
    import numpy as np

    from .data import load_landmarks

    P, keep = [], []
    for e in entries:
        fr = pred.features(*load_landmarks(Path(a.data_root) / e["landmarks_path"]))
        if fr.status != "ok":
            continue
        P.append(pred.predict_features(np.asarray(fr.features, dtype=np.float64)))
        keep.append(e)
    return np.array(P), keep


def cmd_calibrate_open_set(a) -> int:
    """Fit the production unknown-sign detector on (known VALIDATION, unknown part A2), store it in the
    active model's model.json, then evaluate the Predictor's final decisions ONCE on (known TEST, unknown
    part B). Parts A1/A2/B have disjoint glosses; A1 may have trained an "__other__" class."""
    import numpy as np

    from .inference import Predictor
    from .metrics import auroc
    from .openset import detector_features, detector_score, fit_detector

    pred = Predictor.from_registry(Path(a.registry))
    if pred.detector:
        print("active model already has an open_set_detector; refitting")
    by, parts = _entries_and_parts(a, pred)
    feats = lambda P: detector_features(P, pred.known_cols, pred.other_col)  # noqa: E731
    Pv, _ = _probs(a, pred, by["val"])
    Pa2, _ = _probs(a, pred, parts["A2"])
    det = fit_detector(feats(Pv), feats(Pa2), target_far=a.target_far)
    det["fit_parts"] = {"known": "validation split", "unknown": "part A2",
                        "unknown_glosses": len({e["gloss"] for e in parts["A2"]})}

    info_path = pred.dir / "model.json"
    info = json.loads(info_path.read_text())
    baseline_rule = {"tau": pred.tau, "margin": pred.margin}
    info["open_set_detector"] = det
    info_path.write_text(json.dumps(info, indent=2))
    pred2 = Predictor(pred.dir)  # reload exactly as the API will

    Pt, kt = _probs(a, pred2, by["test"])
    Pb, _ = _probs(a, pred2, parts["B"])

    def rates(rule):
        if rule == "detector":
            st_k = [pred2.state_for(p)[0] for p in Pt]
            st_u = [pred2.state_for(p)[0] for p in Pb]
        else:
            pred2.detector = None
            st_k = [pred2.state_for(p)[0] for p in Pt]
            st_u = [pred2.state_for(p)[0] for p in Pb]
            pred2.detector = det
        vocab_idx = {c["sign_id"]: i for i, c in enumerate(pred2.classes)}
        top = [int(np.asarray(pred2.known_cols)[np.argmax(p[pred2.known_cols])]) for p in Pt]
        correct = [t == vocab_idx[e["sign_id"]] for t, e in zip(top, kt, strict=True)]
        rk = np.array([s == "recognized" for s in st_k])
        ru = np.array([s == "recognized" for s in st_u])
        return {"false_rejection": float(1 - rk.mean()), "false_acceptance": float(ru.mean()),
                "known_recognized_and_correct": float((rk & np.array(correct)).mean()),
                "known_recognized_but_wrong": float((rk & ~np.array(correct)).mean()),
                "known_states": dict(Counter(st_k)), "unknown_states": dict(Counter(st_u))}

    sk = detector_score(det, feats(Pt))
    su = detector_score(det, feats(Pb))
    rep = {"model_id": pred2.info["model_id"], "has_other_class": pred2.other_col is not None,
           "protocol": "detector fitted on known validation + unknown part A2; thresholds chosen on that fit set; "
                       "evaluated once on known test + unknown part B (disjoint glosses, never used for any choice)",
           "counts": {"val_known": int(len(Pv)), "unknown_A2": int(len(Pa2)), "test_known": int(len(Pt)),
                      "unknown_B": int(len(Pb)), "glosses_A2": len({e["gloss"] for e in parts["A2"]}),
                      "glosses_B": len({e["gloss"] for e in parts["B"]})},
           "detector": {k: det[k] for k in ("features", "t_recognized", "t_uncertain", "chosen_on_fit_set")},
           "auroc_detector": auroc(sk, su),
           "auroc_maxprob": auroc(np.array([pred2.known_max(p) for p in Pt]), np.array([pred2.known_max(p) for p in Pb])),
           "max_probability_rule": {**baseline_rule, **rates("maxprob")},
           "open_set_detector_rule": rates("detector"),
           "targets": {"false_acceptance_below": 0.10, "false_rejection_at_most": 0.15}}
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "open_set_v3.json").write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep, indent=1))
    return 0


def cmd_ensemble(a) -> int:
    """Build ensembles from trained models in a registry (members chosen by VALIDATION macro-F1)."""
    from .train import build_ensemble

    root = Path(a.registry)
    rows = []
    for d in sorted(p for p in root.iterdir() if (p / "model.json").exists()):
        info = json.loads((d / "model.json").read_text())
        if info["kind"] == "ensemble" or info.get("synthetic"):
            continue
        if info["kind"] not in ("lstm", "gru", "tcn", "transformer", "bilstm_attn"):
            continue
        m = json.loads((d / "metrics.json").read_text())
        rows.append((m["validation"]["macro_f1"], d, info))
    built = []
    groups = sorted({(len(r[2]["classes"]), r[2]["contract"]["version"]) for r in rows})
    for ncls, ver in groups:  # members must share the class list and the feature contract
        group = sorted((r for r in rows if len(r[2]["classes"]) == ncls and r[2]["contract"]["version"] == ver),
                       key=lambda r: -r[0])
        cands = []
        best_per_kind = {}
        for r in group:
            best_per_kind.setdefault(r[2]["kind"], r)
        if len(best_per_kind) >= 2:
            cands.append([r[1] for r in best_per_kind.values()])
        for k in (3, 5):
            if len(group) >= k:
                cands.append([r[1] for r in group[:k]])
        seen = set()
        for c in cands:
            key = tuple(sorted(str(x) for x in c))
            if key in seen:
                continue
            seen.add(key)
            try:
                built.append(build_ensemble(c, Path(a.manifest), Path(a.data_root), root,
                                            dataset_version=a.dataset_version))
            except Exception as exc:  # noqa: BLE001 - one failed candidate must not stop the others
                print(f"[ensemble] skipped {[x.name for x in c]}: {exc}")
    print(json.dumps(built, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("preflight")
    p.add_argument("--out", default="preflight.json")
    p = sub.add_parser("parts")
    p.add_argument("--only", default="", help="comma-separated zip names or category prefixes")
    p = sub.add_parser("extract-part")
    p.add_argument("--part", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--work", default="/tmp/include-work")  # noqa: S108 - runner scratch
    p.add_argument("--hand-model", required=True)
    p.add_argument("--pose-model", required=True)
    p.add_argument("--max-side", type=int, default=960)
    p.add_argument("--face-model", help="face_landmarker.task: also store 22 face points per frame (contract 2.0.0)")
    p.add_argument("--include-reserve", action="store_true", help="also extract the 63 reserve glosses as open-set unknowns")
    p.add_argument("--zip", help="use this already-downloaded, verified zip instead of downloading (it is kept)")
    p = sub.add_parser("merge")
    p.add_argument("--inputs", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--version", default="include-official-v1")
    p = sub.add_parser("compare")
    p.add_argument("--registry", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("fetch-test-videos")
    p.add_argument("--parts", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--work", default="/tmp/include-live")  # noqa: S108 - runner scratch
    p.add_argument("--registry", required=True)
    p.add_argument("--hand-model", required=True)
    p.add_argument("--pose-model", required=True)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--face-model")
    p = sub.add_parser("verify")
    p.add_argument("--registry", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--data-root", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("calibrate-open-set")
    p.add_argument("--registry", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--data-root", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--target-far", type=float, default=0.10)
    p = sub.add_parser("ensemble")
    p.add_argument("--registry", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--data-root", required=True)
    p.add_argument("--dataset-version", default="unversioned")
    p = sub.add_parser("open-set-v2")
    p.add_argument("--registry", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--data-root", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("open-set")
    p.add_argument("--registry", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--data-root", required=True)
    p.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    return {"preflight": cmd_preflight, "parts": cmd_parts, "extract-part": cmd_extract_part,
            "merge": cmd_merge, "compare": cmd_compare, "verify": cmd_verify,
            "fetch-test-videos": cmd_fetch_test_videos, "open-set": cmd_open_set, "open-set-v2": cmd_open_set_v2,
            "calibrate-open-set": cmd_calibrate_open_set, "ensemble": cmd_ensemble}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
