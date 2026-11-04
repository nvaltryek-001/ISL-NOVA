# ISL vocabulary verification protocol

**Status: workflow implemented and tested; 0 of 200 signs linguistically verified.**
No approvals have been made by the developers or by any automated process. Every
slot remains `unverified` until a qualified reviewer signs it off in the app.

## Who may verify

Only accounts holding the `linguist` role can verify or reject a sign (enforced
server-side, `signs:review` permission). Grant this role only to:

* Deaf ISL users with recognised teaching or interpreting experience, or
* ISL interpreters / linguists accredited by a recognised body (for example
  ISLRTC-trained interpreters),

and record the reviewer's qualification outside the app (the app stores the
reviewer's account, timestamp and checklist, not personal credentials).

## What the app enforces

A sign cannot be marked `verified` unless **all** of the following hold
(`POST /api/v1/signs/{id}/review`, decision `verify`):

1. The entry is documented: `linguistic_description`, `hands_required` and
   `movement_type` are filled in. Otherwise the API returns `422 incomplete_entry`
   with `details.missing_fields`, and the UI shows "Document the sign first".
2. The reviewer ticks the three-item checklist (`422 checklist_incomplete` otherwise):
   * **Reference reviewed** — the linked reference video/source was watched.
   * **Form matches reference** — handshape, location, movement, orientation and
     non-manual features described in the entry match the reference.
   * **Meaning confirmed** — the English gloss and translations are an
     appropriate meaning for this ISL sign (regional variants noted).
3. The decision, reviewer, time and checklist are written to the sign's history
   and the audit log; the change is reversible (`reject` / re-review).

`reject` requires a note explaining the problem (wrong form, regional variant,
gloss mismatch, poor reference).

## Working through all 200 signs

1. An admin assigns the `linguist` role (Admin → Users).
2. The reviewer downloads **Explorer → Review sheet (CSV)**
   (`GET /api/v1/signs/review-sheet.csv`), which lists all 200 slots with the
   gloss, category, reference links, current status and empty columns for the
   reviewer's notes. This lets a review team plan and split the work offline.
3. In **Explorer**, filter by status `unverified`, open each sign, complete the
   description fields where needed, and use **Verify** or **Reject** with the
   checklist.
4. Dashboard and Explorer counters show progress (verified / rejected / pending).
5. Disagreements: a second linguist can reject with a note; the history keeps
   both decisions. Resolve by discussion and re-review — do not edit history.

## Relationship to the model

The released model was trained on INCLUDE recordings mapped to the 200 glosses.
Linguistic verification of the vocabulary is a separate, human process. A
`recognized` prediction means "matches INCLUDE examples of this gloss", not
"linguistically verified ISL". The UI and model card say so.

## Tested

* Backend: `test_core_and_signs.py` (incomplete entry → 422, incomplete
  checklist → 422, complete checklist → verified with history; review sheet
  export, permissions) — passing.
* E2E: `app.e2e.mjs` linguist flow (document sign → checklist → verify) — passing.
