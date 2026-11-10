#!/usr/bin/env python3
"""Build the ISL NOVA 200-class vocabulary from the INCLUDE label map.

Provenance
----------
* Glosses, source categories and per-class video counts come from the
  AI4Bharat INCLUDE repository (MIT-licensed code; label map and official
  train/val/test path lists, commit df348f4a640060d4d39f02556d9f96851e8c46c7),
  which describes the INCLUDE dataset (Sridhar et al., ACM MM 2020,
  DOI 10.1145/3394171.3413528, videos on Zenodo record 4010759, CC BY 4.0).
* Planning categories and the 200/263 selection are ISL NOVA project
  decisions, documented in dataset/README.md.

Nothing here is linguistically verified. Every entry is created with
verification_status=reference_found (a labelled external recording exists)
and data_readiness=no_data (no recordings are present locally). Hindi and
Kannada meanings, handshape/movement descriptions and non-manual cues are left
blank on purpose: they require qualified ISL review and must not be guessed.

The script is idempotent: if signs_master.csv already exists, existing
sign_id assignments are preserved and only derived counts are refreshed.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sources" / "include"
VOCAB = ROOT / "vocabulary"
MANIFESTS = ROOT / "manifests"

INCLUDE_COMMIT = "df348f4a640060d4d39f02556d9f96851e8c46c7"
INCLUDE_DOI = "10.1145/3394171.3413528"
INCLUDE_ZENODO = "https://zenodo.org/records/4010759"
INCLUDE_LICENSE = "CC BY 4.0 (dataset videos); MIT (label map / split files)"
INCLUDE_ATTRIBUTION = (
    "INCLUDE: A Large Scale Dataset for Indian Sign Language Recognition - "
    "Sridhar, Ganesan, Kumar, Khapra (ACM MM 2020); AI4Bharat / IIT Madras"
)

# Planning categories (ordered). Targets follow the master specification;
# actual counts depend on what an authentic, licensed source covers.
CATEGORIES: list[tuple[str, str, int]] = [
    ("greetings_social", "Greetings / social expressions", 20),
    ("people_family", "People / family / relationships", 20),
    ("everyday_actions", "Everyday actions", 25),
    ("objects_places", "Objects / places", 20),
    ("daily_needs", "Food / daily needs", 20),
    ("numbers_time", "Numbers / time / calendar", 20),
    ("emotions_states", "Emotions / feelings / states", 20),
    ("communication", "Questions / communication / pronouns", 20),
    ("education_work", "Education / work / professions", 20),
    ("travel_emergency", "Travel / directions / emergencies", 15),
    ("descriptions_colours", "Descriptions / colours (added: source coverage)", 0),
    ("animals_nature", "Animals / nature (added: source coverage)", 0),
]

ASSIGN: dict[str, list[str]] = {
    "greetings_social": [
        "hello", "howareyou", "goodmorning", "goodafternoon", "goodevening",
        "goodnight", "thankyou", "alright", "pleased", "nice", "good", "bad",
        "friend", "neighbour", "gift", "marriage", "god", "peace", "sign",
        "deaf", "blind", "religion",
    ],
    "people_family": [
        "mother", "father", "brother", "sister", "son", "daughter",
        "grandfather", "grandmother", "husband", "wife", "parent", "family",
        "baby", "child", "boy", "girl", "man", "woman", "adult", "young",
        "old", "male", "female", "crowd", "king", "queen", "raceethnicity",
    ],
    "everyday_actions": [
        "exercise", "paint", "dream", "sport", "attack", "war", "election",
    ],
    "objects_places": [
        "bag", "ball", "bed", "bedroom", "bathroom", "box", "chair", "clock",
        "door", "fan", "key", "kitchen", "lamp", "lock", "ring", "table",
        "window", "house", "ground", "park", "market", "city", "india",
        "court", "office", "restaurant", "storeorshop", "bank", "temple",
        "camera", "computer", "laptop", "mouse", "screen", "tool", "gun",
        "page", "card", "photograph",
    ],
    "daily_needs": [
        "medicine", "soap", "money", "bill", "price", "cheap", "expensive",
        "rich", "poor", "clothing", "dress", "shirt", "tshirt", "pant",
        "skirt", "suit", "shoes", "hat", "pocket",
    ],
    "numbers_time": [
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
        "sunday", "today", "tomorrow", "yesterday", "morning", "afternoon",
        "evening", "night", "time", "hour", "minute", "second",
        "secondnumber", "week", "month", "year", "season", "spring",
        "summer", "winter", "fall", "exmonsoon",
    ],
    "emotions_states": [
        "happy", "sad", "beautiful", "ugly", "sick", "healthy", "alive",
        "dead", "death", "cold", "hot", "warm", "cool", "quiet", "loud",
        "strong", "weak", "famous", "mean",
    ],
    "communication": [
        "i", "you", "he", "she", "it", "we", "they", "youplural", "letter",
        "newspaper", "telephone", "cellphone", "radio", "television",
    ],
    "education_work": [
        "teacher", "student", "school", "university", "library", "book",
        "pen", "pencil", "paper", "science", "technology", "energy", "job",
        "doctor", "lawyer", "manager", "secretary", "waiter", "artist",
        "actor", "author", "soldier", "president", "patient", "reporter",
        "priest", "player", "team",
    ],
    "travel_emergency": [
        "bus", "car", "train", "plane", "boat", "bicycle", "truck",
        "trainstation", "trainticket", "transportation", "streetorroad",
        "location", "hospital", "police",
    ],
    "descriptions_colours": [
        "black", "blue", "brown", "green", "grey", "orange", "pink", "red",
        "white", "yellow", "colour", "biglarge", "smalllittle", "tall",
        "short", "long", "high", "low", "heavy", "light", "new", "clean",
        "dirty", "dry", "wet", "hard", "soft", "thick", "thin", "wide",
        "narrow", "deep", "shallow", "flat", "curved", "loose", "tight",
        "fast", "slow",
    ],
    "animals_nature": ["animal", "bird", "cat", "cow", "dog", "fish", "horse"],
}

# 63 INCLUDE glosses held in reserve (not assigned a slot). Reasons are
# recorded in reserve_candidates.csv. Criteria: lexical ambiguity in English
# gloss, overlap with another gloss, lower everyday-communication priority.
RESERVE: dict[str, str] = {
    "raceethnicity": "sensitive/abstract; needs community review before use",
    "secondnumber": "ambiguous with 'second' (time); keep one",
    "exmonsoon": "source gloss unclear",
    "mouse": "ambiguous (animal vs computer device)",
    "mean": "ambiguous English gloss (unkind vs average)",
    "light": "ambiguous English gloss (weight vs illumination)",
    "fall": "ambiguous English gloss (season vs action)",
    "curved": "low communication priority",
    "shallow": "low communication priority",
    "deep": "low communication priority",
    "flat": "ambiguous (apartment vs level)",
    "thick": "low communication priority",
    "thin": "low communication priority",
    "wide": "low communication priority",
    "narrow": "low communication priority",
    "loose": "low communication priority",
    "tight": "low communication priority",
    "gun": "violence-related; low priority for assistive use",
    "attack": "violence-related; low priority for assistive use",
    "war": "violence-related; low priority for assistive use",
    "election": "low everyday priority",
    "president": "low everyday priority",
    "king": "low everyday priority",
    "queen": "low everyday priority",
    "court": "low everyday priority",
    "tool": "generic gloss",
    "page": "low everyday priority",
    "card": "ambiguous gloss",
    "screen": "low everyday priority",
    "energy": "abstract",
    "science": "abstract",
    "technology": "abstract",
    "actor": "low everyday priority",
    "author": "low everyday priority",
    "artist": "low everyday priority",
    "secretary": "low everyday priority",
    "reporter": "low everyday priority",
    "soldier": "low everyday priority",
    "crowd": "low everyday priority",
    "male": "overlaps with 'man'",
    "female": "overlaps with 'woman'",
    "adult": "overlaps with 'man'/'woman'",
    "ground": "ambiguous gloss",
    "ring": "ambiguous (jewellery vs phone ring)",
    "lamp": "overlaps with light-related signs",
    "box": "low everyday priority",
    "suit": "low everyday priority",
    "skirt": "low everyday priority",
    "colour": "generic; colour names kept instead",
    "alive": "low everyday priority",
    "death": "overlaps with 'dead'",
    "famous": "low everyday priority",
    "cool": "ambiguous (temperature vs slang)",
    "peace": "abstract",
    "religion": "abstract",
    "temple": "low everyday priority",
    "priest": "low everyday priority",
    "god": "abstract",
    "team": "low everyday priority",
    "player": "low everyday priority",
    "pocket": "low everyday priority",
    "dream": "abstract",
    "paint": "ambiguous (verb vs noun)",
}

MASTER_FIELDS = [
    "sign_id", "canonical_sign_name", "source_gloss", "category",
    "category_label", "source_category", "english_meaning", "hindi_meaning",
    "kannada_meaning", "linguistic_description", "reference_source",
    "reference_media", "source_license", "attribution", "dominant_hand",
    "hands_required", "movement_type", "body_movement", "non_manual_cue",
    "regional_variation", "annotation_notes", "verification_status",
    "reviewer", "approval_date", "local_sample_count", "local_signer_count",
    "local_session_count", "external_train_videos", "external_val_videos",
    "external_test_videos", "split_assignment", "data_readiness",
    "training_eligible",
]

PENDING = ""  # explicit blank = not yet known; never fabricated


def _norm(folder: str) -> str:
    return "".join(ch for ch in folder if ch.isalpha()).lower()


def read_include() -> tuple[dict[str, int], dict[str, dict]]:
    label_map = json.loads((SRC / "label_map_include.json").read_text())
    info: dict[str, dict] = defaultdict(
        lambda: {"display": None, "category": None, "train": 0, "val": 0, "test": 0}
    )
    for split in ("train", "val", "test"):
        for line in (SRC / f"include_{split}.txt").read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            cat, folder, _file = line.split("/", 2)
            gloss = _norm(folder)
            entry = info[gloss]
            disp = re.sub(r"^\d+\.\s*", "", folder).strip()
            entry["display"] = disp[:1].upper() + disp[1:]
            entry["category"] = cat.replace("_", " ")
            entry[split] += 1
    return label_map, info


def build() -> dict:
    label_map, info = read_include()
    assigned = [g for gl in ASSIGN.values() for g in gl]
    dupes = [g for g, n in Counter(assigned).items() if n > 1]
    assert not dupes, f"gloss assigned twice: {dupes}"
    unknown = set(assigned) - set(label_map)
    assert not unknown, f"gloss not in INCLUDE label map: {unknown}"
    missing = set(label_map) - set(assigned)
    assert not missing, f"INCLUDE gloss without category: {missing}"
    assert set(RESERVE) <= set(label_map)

    cat_of = {g: c for c, gl in ASSIGN.items() for g in gl}
    cat_label = {c: lbl for c, lbl, _ in CATEGORIES}
    order = [c for c, _, _ in CATEGORIES]
    selected = sorted(
        (g for g in label_map if g not in RESERVE),
        key=lambda g: (order.index(cat_of[g]), g),
    )
    assert len(selected) == 200, f"expected 200 selected glosses, got {len(selected)}"

    master_path = VOCAB / "signs_master.csv"
    existing: dict[str, str] = {}
    if master_path.exists():
        with master_path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                existing[row["source_gloss"]] = row["sign_id"]
                # preserve human-entered fields on regeneration
                existing[f"__row__{row['source_gloss']}"] = row  # type: ignore[assignment]

    used = {v for k, v in existing.items() if not k.startswith("__row__")}
    next_n = 1
    rows = []
    for gloss in selected:
        sid = existing.get(gloss)
        if not sid:
            while f"ISL{next_n:03d}" in used:
                next_n += 1
            sid = f"ISL{next_n:03d}"
            used.add(sid)
        meta = info[gloss]
        prev = existing.get(f"__row__{gloss}") or {}
        row = {f: PENDING for f in MASTER_FIELDS}
        row.update(
            {
                "sign_id": sid,
                "canonical_sign_name": meta["display"] or gloss,
                "source_gloss": gloss,
                "category": cat_of[gloss],
                "category_label": cat_label[cat_of[gloss]],
                "source_category": meta["category"] or "",
                "english_meaning": meta["display"] or gloss,
                "reference_source": f"INCLUDE ({INCLUDE_ZENODO}; doi:{INCLUDE_DOI})",
                "reference_media": "INCLUDE videos (external, not redistributed in this repository)",
                "source_license": INCLUDE_LICENSE,
                "attribution": INCLUDE_ATTRIBUTION,
                "annotation_notes": "English gloss taken from INCLUDE folder name; ISL form, regional variants and non-manual cues require qualified review.",
                "verification_status": "reference_found",
                "local_sample_count": "0",
                "local_signer_count": "0",
                "local_session_count": "0",
                "external_train_videos": str(meta["train"]),
                "external_val_videos": str(meta["val"]),
                "external_test_videos": str(meta["test"]),
                "split_assignment": "INCLUDE official split (train/val/test path lists)",
                "data_readiness": "no_data",
                "training_eligible": "false",
            }
        )
        # keep any reviewed human input
        for k in (
            "hindi_meaning", "kannada_meaning", "linguistic_description",
            "dominant_hand", "hands_required", "movement_type", "body_movement",
            "non_manual_cue", "regional_variation", "reviewer", "approval_date",
        ):
            if prev.get(k):
                row[k] = prev[k]
        if prev.get("verification_status") in {"review_pending", "verified", "rejected"}:
            row["verification_status"] = prev["verification_status"]
        rows.append(row)

    rows.sort(key=lambda r: r["sign_id"])
    ids = [r["sign_id"] for r in rows]
    assert ids == [f"ISL{i:03d}" for i in range(1, 201)], "IDs must be ISL001..ISL200"

    VOCAB.mkdir(parents=True, exist_ok=True)
    MANIFESTS.mkdir(parents=True, exist_ok=True)
    _write(master_path, MASTER_FIELDS, rows)
    _write(
        VOCAB / "translations.csv",
        ["sign_id", "language", "text", "status", "translator", "reviewer", "source", "notes"],
        [
            {"sign_id": r["sign_id"], "language": lang, "text": text, "status": st,
             "translator": "", "reviewer": "", "source": src, "notes": note}
            for r in rows
            for lang, text, st, src, note in (
                ("en", r["english_meaning"], "source_gloss", "INCLUDE folder name", "English gloss from source; not a verified ISL translation"),
                ("hi", "", "pending", "", "Requires bilingual reviewer familiar with ISL usage"),
                ("kn", "", "pending", "", "Requires bilingual reviewer familiar with ISL usage"),
            )
        ],
    )
    _write(
        VOCAB / "references.csv",
        ["sign_id", "source_name", "source_url", "doi", "license", "media_type", "redistribution", "training_permitted", "notes"],
        [
            {"sign_id": r["sign_id"], "source_name": "INCLUDE", "source_url": INCLUDE_ZENODO,
             "doi": INCLUDE_DOI, "license": "CC BY 4.0", "media_type": "video (external)",
             "redistribution": "permitted with attribution (CC BY 4.0); not mirrored here",
             "training_permitted": "yes, with attribution (CC BY 4.0)",
             "notes": f"{r['external_train_videos']}/{r['external_val_videos']}/{r['external_test_videos']} train/val/test videos listed in official split files"}
            for r in rows
        ],
    )
    log_path = VOCAB / "verification_log.csv"
    if not log_path.exists():
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        _write(
            log_path,
            ["timestamp_utc", "sign_id", "from_status", "to_status", "actor", "note"],
            [
                {"timestamp_utc": now, "sign_id": r["sign_id"], "from_status": "",
                 "to_status": "reference_found", "actor": "build_vocabulary.py",
                 "note": "Slot created from INCLUDE label map; awaiting qualified ISL review"}
                for r in rows
            ],
        )
    _write(
        VOCAB / "reserve_candidates.csv",
        ["source_gloss", "source_category", "reason", "external_videos"],
        [
            {"source_gloss": g, "source_category": info[g]["category"] or "",
             "reason": RESERVE[g],
             "external_videos": str(info[g]["train"] + info[g]["val"] + info[g]["test"])}
            for g in sorted(RESERVE)
        ],
    )
    _write(
        VOCAB / "categories.csv",
        ["category", "label", "planning_target", "assigned_slots"],
        [
            {"category": c, "label": lbl, "planning_target": str(t),
             "assigned_slots": str(sum(1 for r in rows if r["category"] == c))}
            for c, lbl, t in CATEGORIES
        ],
    )

    summary = {
        "class_slots": len(rows),
        "verified": sum(r["verification_status"] == "verified" for r in rows),
        "reference_found": sum(r["verification_status"] == "reference_found" for r in rows),
        "classes_with_local_recordings": 0,
        "approved_for_training": 0,
        "local_recordings": 0,
        "external_videos_listed": sum(
            int(r["external_train_videos"]) + int(r["external_val_videos"]) + int(r["external_test_videos"])
            for r in rows
        ),
    }
    version = {
        "dataset_name": "isl-nova-vocabulary",
        "version": "0.1.0",
        "created_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "vocabulary_only",
        "description": "200 class slots derived from the INCLUDE label map. No local recordings; not approved for training.",
        "source": {"name": "INCLUDE", "commit": INCLUDE_COMMIT, "doi": INCLUDE_DOI,
                   "zenodo": INCLUDE_ZENODO, "license": INCLUDE_LICENSE},
        "summary": summary,
    }
    manifest_path = MANIFESTS / "dataset_manifest.json"
    manifest = {
        "schema_version": 1,
        "dataset_version": version["version"],
        "feature_contract": "isl-nova-fc-1.0.0",
        "classes": [{"sign_id": r["sign_id"], "gloss": r["source_gloss"], "category": r["category"]} for r in rows],
        "entries": [],
        "notes": "entries[] lists approved local or imported recordings; it is empty because none exist yet.",
    }
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text())
        manifest["entries"] = old.get("entries", [])
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    vpath = MANIFESTS / "dataset_version.json"
    if vpath.exists():
        version["created_utc"] = json.loads(vpath.read_text()).get("created_utc", version["created_utc"])
    vpath.write_text(json.dumps(version, indent=2) + "\n")
    return summary


def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
