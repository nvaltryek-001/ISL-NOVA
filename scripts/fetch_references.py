#!/usr/bin/env python3
"""Install sign reference data (Practice Coach, Text-to-Sign) from the GitHub release.

    python scripts/fetch_references.py [--dir dataset/references] [--tag references-v1]

Downloads references_v1.npz and its .sha256, verifies the checksum and writes
both into --dir (default: REFERENCES_DIR or dataset/references). Derived from
the INCLUDE training split (CC BY 4.0); landmarks only, no video.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "nvaltryek-001/ISL-NOVA"


def get(url: str) -> bytes:
    if not url.startswith("https://"):
        raise SystemExit(f"refusing non-https URL {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "isl-nova-fetch-references"})  # noqa: S310
    with urllib.request.urlopen(req, timeout=300) as r:  # noqa: S310
        return r.read()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, default=Path(os.environ.get("REFERENCES_DIR") or ROOT / "dataset" / "references"))
    ap.add_argument("--tag", default="references-v1")
    a = ap.parse_args(argv)
    base = f"https://github.com/{REPO}/releases/download/{a.tag}"
    target = a.dir / "references_v1.npz"
    want = get(f"{base}/references_v1.npz.sha256").decode().split()[0]
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == want:
        print(f"references already installed in {a.dir}")
        return 0
    blob = get(f"{base}/references_v1.npz")
    got = hashlib.sha256(blob).hexdigest()
    if got != want:
        print(f"checksum mismatch: expected {want}, got {got}", file=sys.stderr)
        return 1
    a.dir.mkdir(parents=True, exist_ok=True)
    target.write_bytes(blob)
    print(f"installed references ({len(blob) / 1e6:.1f} MB, SHA-256 verified) in {a.dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
