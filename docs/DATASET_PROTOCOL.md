# Dataset protocol

## 1. Source audit

Each source was checked for publication, access method, licence, redistribution and training rights, consent scope, vocabulary fit, annotation format and whether signer IDs are available for a split.

| Source | Verified facts | Licence | Training permitted | Signer IDs | Decision |
|---|---|---|---|---|---|
| **INCLUDE** (AI4Bharat / IIT Madras, ACM MM 2020, doi:10.1145/3394171.3413528) | 263 isolated word signs, 15 categories, 4,292 videos, recorded with deaf students of St. Louis School for the Deaf, Chennai; official train/test split (+ val list in the code repo) | CC BY 4.0 (Zenodo 4010759); code MIT | Yes, with attribution | **Not published** | **Adopted** as the vocabulary source and the first training-data source |
| **iSign** (Joshi et al., Findings of ACL 2024, doi:10.18653/v1/2024.findings-acl.643) | ISL-English video/sentence pairs, pose files, 5 tasks; ~228 GB; gated on Hugging Face | CC BY-NC-SA 4.0 | Research, non-commercial only; share-alike | Not reviewed | Not adopted: continuous-sentence data, non-commercial terms. Possible future research comparison. |
| **GloSL** | Could not identify a resource of this name during the audit | - | - | - | Blocked: needs a link from the project owner |
| ISLRTC ISL Dictionary (Govt. of India; 3rd edition reported at 10,000 terms) | Official dictionary; videos viewable online | Not established | **Not established** | - | Not used. Public viewing does not grant reuse. Requires written permission from ISLRTC. |
| CISLR (IIT Kanpur, Hugging Face, gated) | Gated dataset requiring contact sharing | Not reviewed | Not reviewed | - | Identified only |
| Mendeley ISL datasets (e.g. "ISL Hand Gesture Dataset", "ISLVT") | Listed on Mendeley Data | Per-record | Not reviewed | - | Identified only |

Nothing was scraped, and no access control was bypassed. No data from any source is committed to this repository.

## 2. Importing INCLUDE (user action required)

1. Download the category archives from <https://zenodo.org/records/4010759> (56.8 GB) and extract them to e.g. `/data/INCLUDE/<Category>/<NN. Word>/MVI_xxxx.MOV`.
2. Download MediaPipe `hand_landmarker.task` and `pose_landmarker_lite.task` from Google's MediaPipe model pages.
3. Run the importer. It extracts landmarks only for the 200 ISL NOVA classes and keeps INCLUDE's official split:

   ```bash
   PYTHONPATH=ml python -m isl_nova_ml.include_import --include-root /data/INCLUDE \
       --out data/processed/include --hand-model models/hand_landmarker.task \
       --pose-model models/pose_landmarker_lite.task            # add --limit 50 for a dry run
   ```

4. Review the import report (`failures`, per-video `quality`), then re-run with `--approve` to record the reviewer decision.
5. Train (see [MODEL_CARD.md](MODEL_CARD.md)).

> **Caveat:** INCLUDE does not publish signer IDs. Entries get `signer_id = unknown:include`, so the official split's **signer independence cannot be verified**. Every model trained on it records this in its lineage. Results must be reported as *INCLUDE official split*, not as signer-independent.

## 3. Recording new data (Recording Studio)

1. **Register a pseudonymous signer.** The record holds a random code plus optional dominant hand, age band, region and hearing status. No names or contact details.
2. **Record informed consent** with the `isl-nova-consent-v1` text, explained in ISL. Scopes: `recording_storage` (required), `model_training`, `research_display`, `public_reference_media`. There is an optional retention date, and the signer must explicitly confirm.
3. **Open a session** with environment metadata (lighting, background, camera distance).
4. **Record.** After a 3-second countdown the studio captures a 2.5-second clip. Hand and pose landmarks are extracted in the browser at the same time. Signers vary lighting, distance, speed and (where linguistically appropriate) hand across sessions.
5. **Automatic checks on upload:** magic-byte container check (MP4/WebM/MOV only), size limit, full decode with OpenCV, duration 0.5–12 s, resolution ≥ 320×240, FPS ≥ 15, exact-duplicate SHA-256, landmark sufficiency (≥ 8 frames, hands in ≥ 25 % of frames).
6. **Annotation and four-eyes review.** One person labels the clip. A *different* reviewer with the linguist or admin role approves or rejects it. A label that disagrees with the requested sign rejects the recording.
7. **Readiness** is recomputed for the class after every change.

## 4. Validation (`POST /api/v1/dataset/validate`)

Checks: all 200 slots active · media present · SHA-256 integrity · duplicate hashes · recordings under revoked consent · signer independence (≥ 3 signers) · class imbalance (> 5× spread).

## 5. Versioning and manifests

`POST /api/v1/dataset/versions` freezes all **approved** recordings that have landmarks and **`model_training` consent**. It assigns a deterministic **signer-independent** split (seeded), runs the leakage report, stores the manifest JSON in object storage with its SHA-256, and records `manifest_entries` rows. Versions are immutable. The manifest feeds `isl_nova_ml.train` directly.
