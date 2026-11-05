# ISL NOVA dataset

This folder holds the **vocabulary** and **manifests** of the ISL NOVA dataset. It never holds videos, landmark files or signer data: those live in object storage and are referenced by key.

## What exists today (honest status)

| Metric | Value | Meaning |
|---|---:|---|
| Class slots created | **200** | `ISL001` – `ISL200`, stable IDs |
| Linguistically verified entries | **0** | No qualified ISL reviewer has signed off yet |
| Entries with a licensed reference source | 200 | Each maps to an INCLUDE class (CC BY 4.0) |
| External videos listed for these classes | 3,392 | INCLUDE's official train/val/test path lists |
| INCLUDE videos processed | 3,370 usable sequences | Downloaded and landmark-extracted on GitHub Actions (data run 41764539272); raw video never stored in the repo |
| Classes with local (app-recorded) recordings | 0 | |
| Classes approved through the in-app workflow | 0 | needs linguistic verification first |
| Classes trained / evaluated | **200 / 200** | LSTM, INCLUDE official split; see docs/MODEL_CARD.md |

The live, per-class numbers are always available at `GET /api/v1/dataset/stats` and in the Dataset Lab.

## Files

| File | Contents |
|---|---|
| `vocabulary/signs_master.csv` | One row per slot with every field from the specification. Unknown linguistic fields are **blank on purpose**. |
| `vocabulary/translations.csv` | en / hi / kn per sign. English = source gloss (`status=source_gloss`); Hindi and Kannada are `pending`. |
| `vocabulary/references.csv` | Source, DOI, licence and training permission per sign. |
| `vocabulary/verification_log.csv` | Status transitions at creation time (later transitions are recorded in the database). |
| `vocabulary/categories.csv` | Planning targets vs. slots actually assigned. |
| `vocabulary/reserve_candidates.csv` | The 63 INCLUDE glosses *not* given a slot, with the reason. |
| `manifests/dataset_manifest.json` | Class list + approved entries (empty) for the versioned dataset. |
| `manifests/dataset_version.json` | Version metadata and summary counts. |
| `sources/include/` | INCLUDE label map and official split lists (MIT licence, AI4Bharat), commit `df348f4`. |
| `scripts/build_vocabulary.py` | Deterministic, idempotent generator for the files above. |

## How the 200 slots were chosen

INCLUDE provides 263 word classes in 15 categories. ISL NOVA keeps **200** of them for everyday communication and holds 63 in reserve (ambiguous English glosses such as *mouse* or *light*, near-duplicates such as *male/man*, violence-related and low-priority vocabulary). Each kept gloss was mapped to one of the project's planning categories.

The planning targets from the specification could not all be met from a single licensed source. In particular, INCLUDE has few **everyday action verbs** and no **food** or **question** words. Two extra categories (*descriptions/colours*, *animals/nature*) absorb INCLUDE classes that fit nowhere else. `categories.csv` shows the target and the actual count side by side. Closing the gaps needs new consented recordings or another licensed source.

## Statuses

* `verification_status`: `proposed` → `reference_found` → `review_pending` → `verified` (or `rejected`). Only users with the **linguist** role can set `verified`.
* `data_readiness`: `no_data`, `collecting`, `insufficient_data`, `ready_for_review`, `approved_for_training`, `excluded`. It is computed by the server from approved recordings: **approved_for_training needs a verified sign, ≥ 10 approved recordings and ≥ 3 distinct signers.**

## Regenerating

```bash
python dataset/scripts/build_vocabulary.py
```

Existing `sign_id` assignments and any human-entered fields are preserved; CI checks the output is reproducible.

## Attribution

Glosses and split lists derive from **INCLUDE: A Large Scale Dataset for Indian Sign Language Recognition**, A. Sridhar, R. G. Ganesan, P. Kumar, M. Khapra, ACM Multimedia 2020, doi:[10.1145/3394171.3413528](https://doi.org/10.1145/3394171.3413528). Videos: [Zenodo 4010759](https://zenodo.org/records/4010759), CC BY 4.0.
