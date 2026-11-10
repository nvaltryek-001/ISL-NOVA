#!/usr/bin/env python3
"""Merge machine-drafted Hindi and Kannada meanings into translations.csv.

    python dataset/scripts/draft_translations.py

Reads dataset/vocabulary/drafts/hi_kn_machine_drafts.csv and fills only rows
that are still empty and `pending`. Rows a person has written, reviewed,
verified or rejected are never overwritten. Drafts are stored with
status `draft` and source `machine draft`: they are NOT verified meanings and
must be reviewed by native speakers (and approved by a linguist in the app).
Re-running is idempotent.
"""
from __future__ import annotations

import csv
from pathlib import Path

VOCAB = Path(__file__).resolve().parents[1] / "vocabulary"
COLS = ["sign_id", "language", "text", "transliteration", "status", "translator", "reviewer", "source", "notes"]


def main() -> int:
    drafts = {r["sign_id"]: r for r in csv.DictReader((VOCAB / "drafts" / "hi_kn_machine_drafts.csv").open(encoding="utf-8"))}
    path = VOCAB / "translations.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    filled = 0
    for r in rows:
        r.setdefault("transliteration", "")
        d = drafts.get(r["sign_id"])
        if not d or r["language"] not in ("hi", "kn"):
            continue
        if r["status"] == "pending" and not r["text"].strip():
            r.update(text=d[r["language"]], transliteration=d[f"{r['language']}_translit"], status="draft",
                     translator="machine", source="machine draft (ISL NOVA v2)",
                     notes="Machine-drafted word meaning; needs native-speaker review and linguist approval")
            filled += 1
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c) or "" for c in COLS})
    print(f"filled {filled} draft rows; total {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
