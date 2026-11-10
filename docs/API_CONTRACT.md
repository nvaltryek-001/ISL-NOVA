# API contract

Generated from the application's OpenAPI document by `scripts/gen_api_contract.py`, so it always matches the code. The machine-readable spec is served at `/api/v1/openapi.json` and an interactive viewer at `/api/docs`.

* Base path: `/api/v1`. JSON in and out (multipart for uploads).
* Auth: `Authorization: Bearer <JWT>` from `POST /auth/login` or `/auth/register`.
* Errors: `{"error": {"code", "message", "details?"}}` with 401 / 403 / 404 / 409 / 413 / 415 / 422 / 429.
* **Auth** column: `public`, `optional` (works anonymously, richer when signed in) or `required`. **Permission** is enforced server-side.

## core

| Method | Path | Summary | Auth | Permission |
|---|---|---|---|---|
| `GET` | `/api/v1/health` | Service health | public | - |
| `POST` | `/api/v1/auth/register` | Create an account (learner role) | public | - |
| `POST` | `/api/v1/auth/login` | Exchange credentials for an access token | public | - |
| `POST` | `/api/v1/auth/logout-all` | Sign out everywhere: revoke every token issued to this account | required | - |
| `POST` | `/api/v1/me/2fa/setup` | Start two-factor setup: a new TOTP secret (not active until confirmed) | required | - |
| `POST` | `/api/v1/me/2fa/enable` | Confirm a code from the authenticator app and turn two-factor on | required | - |
| `POST` | `/api/v1/me/2fa/disable` | Turn two-factor off (needs a current code) | required | - |
| `GET` | `/api/v1/me` | Current user profile | required | - |
| `PATCH` | `/api/v1/me` | Update profile, preferences or password | required | - |
| `GET` | `/api/v1/notifications` | My notifications | required | - |
| `POST` | `/api/v1/notifications/{nid}/read` | Mark a notification read | required | - |
| `GET` | `/api/v1/admin/users` | List users | required | `admin:users` |
| `PATCH` | `/api/v1/admin/users/{uid}` | Change roles or deactivate a user | required | `admin:users` |
| `POST` | `/api/v1/admin/users/{uid}/password-reset` | Issue a one-time password reset code (30 min) | required | `admin:users` |
| `POST` | `/api/v1/auth/reset-password` | Set a new password with a one-time reset code | public | - |
| `POST` | `/api/v1/admin/retention` | Run the data-retention job (dry run unless apply=true) | required | `admin:users` |
| `GET` | `/api/v1/admin/audit` | Audit log | required | `admin:audit` |
| `GET` | `/api/v1/admin/roles` | Roles and permissions | required | `admin:users` |

## signs

| Method | Path | Summary | Auth | Permission |
|---|---|---|---|---|
| `GET` | `/api/v1/signs` | Search and filter the vocabulary | optional | - |
| `POST` | `/api/v1/signs` | Create a vocabulary entry | required | `signs:write` |
| `GET` | `/api/v1/signs/review-sheet.csv` | CSV review sheet of all signs for offline linguistic review | required | `signs:review` |
| `GET` | `/api/v1/signs/categories` | Categories with slot counts | public | - |
| `GET` | `/api/v1/signs/{sign_id}` | Sign detail with references, translations and history | optional | - |
| `PATCH` | `/api/v1/signs/{sign_id}` | Update descriptive fields of a sign | required | `signs:write` |
| `DELETE` | `/api/v1/signs/{sign_id}` | Retire a sign (soft delete; ids are never reused) | required | `signs:write` |
| `POST` | `/api/v1/signs/{sign_id}/restore` | Restore a retired sign | required | `signs:write` |
| `POST` | `/api/v1/signs/{sign_id}/review` | Move a sign through the verification workflow | required | `signs:review` |
| `PUT` | `/api/v1/signs/{sign_id}/translations/{lang}` | Set a meaning in en/hi/kn | required | `translations:write` |
| `POST` | `/api/v1/signs/{sign_id}/references` | Attach a licensed reference source | required | `signs:write` |
| `DELETE` | `/api/v1/signs/{sign_id}/references/{rid}` | Remove a reference | required | `signs:write` |
| `GET` | `/api/v1/bookmarks` | My bookmarked signs | required | - |
| `PUT` | `/api/v1/bookmarks/{sign_id}` | Bookmark a sign | required | - |
| `DELETE` | `/api/v1/bookmarks/{sign_id}` | Remove a bookmark | required | - |

## translations

| Method | Path | Summary | Auth | Permission |
|---|---|---|---|---|
| `GET` | `/api/v1/translations/coverage` | Meanings per language and review status | optional | - |
| `GET` | `/api/v1/translations/review-sheet.csv` | CSV of all en/hi/kn meanings for native-speaker review | required | `translations:write` |
| `POST` | `/api/v1/translations/import` | Apply a reviewed translation sheet (new_text / new_status columns) | required | `translations:write` |

## proposals

| Method | Path | Summary | Auth | Permission |
|---|---|---|---|---|
| `POST` | `/api/v1/vocabulary/proposals` | Propose a new vocabulary sign | required | - |
| `GET` | `/api/v1/vocabulary/proposals` | List proposals (reviewers see all, others their own) | required | - |
| `POST` | `/api/v1/vocabulary/proposals/{pid}/decide` | Accept or reject a proposal | required | `signs:write` |

## dataset

| Method | Path | Summary | Auth | Permission |
|---|---|---|---|---|
| `GET` | `/api/v1/dataset/stats` | Truthful dataset readiness statistics | public | - |
| `GET` | `/api/v1/dataset/signs` | Per-class readiness table | required | `dataset:read` |
| `GET` | `/api/v1/dataset/signers` | Pseudonymous signers | required | `dataset:read` |
| `POST` | `/api/v1/dataset/signers` | Register a pseudonymous signer (no names or contact data) | required | `dataset:write` |
| `DELETE` | `/api/v1/dataset/signers/{sid}` | Erase a signer and all their media | required | `dataset:write` |
| `POST` | `/api/v1/dataset/signers/{sid}/consents` | Record informed consent | required | `dataset:write` |
| `POST` | `/api/v1/dataset/consents/{cid}/revoke` | Withdraw consent (erases that signer's media) | required | `dataset:write` |
| `GET` | `/api/v1/dataset/sessions` | Recording sessions | required | `dataset:read` |
| `POST` | `/api/v1/dataset/sessions` | Open a recording session | required | `dataset:write` |
| `POST` | `/api/v1/dataset/recordings` | Upload a consented recording (video + optional landmarks) | required | `dataset:write` |
| `GET` | `/api/v1/dataset/recordings` | List recordings | required | `dataset:read` |
| `GET` | `/api/v1/dataset/recordings/{rid}` | Recording detail | required | `dataset:read` |
| `DELETE` | `/api/v1/dataset/recordings/{rid}` | Delete a recording and its media | required | `dataset:write` |
| `GET` | `/api/v1/dataset/recordings/{rid}/media` | Stream recording media to authorised reviewers | required | `dataset:review` |
| `GET` | `/api/v1/annotations` | Annotation review queue | required | `dataset:read` |
| `POST` | `/api/v1/annotations` | Annotate a recording | required | `dataset:write` |
| `PATCH` | `/api/v1/annotations/{aid}` | Review an annotation (four-eyes: not your own) | required | `dataset:review` |
| `POST` | `/api/v1/dataset/validate` | Run dataset integrity, consent and leakage checks | required | `dataset:read` |
| `GET` | `/api/v1/dataset/versions` | Dataset versions | required | `dataset:read` |
| `POST` | `/api/v1/dataset/versions` | Freeze approved, consented recordings into a versioned manifest | required | `dataset:version` |
| `GET` | `/api/v1/dataset/versions/{vid}/manifest` | Export a version's training manifest | required | `dataset:read` |
| `GET` | `/api/v1/dataset/feature-contract` | Active feature contract definition | public | - |

## ml

| Method | Path | Summary | Auth | Permission |
|---|---|---|---|---|
| `GET` | `/api/v1/model/info` | Active model status (never fabricated) | public | - |
| `GET` | `/api/v1/model/metrics` | Held-out metrics of the active model | public | - |
| `GET` | `/api/v1/evaluation/metrics` | Per-class held-out evaluation | public | - |
| `GET` | `/api/v1/evaluation/confusion-matrix` | Test-set confusion matrix | public | - |
| `POST` | `/api/v1/predict/sequence` | Classify a landmark sequence | optional | - |
| `POST` | `/api/v1/predict` | Classify the current window (alias of /predict/sequence) | optional | - |
| `GET` | `/api/v1/models` | Model registry | required | `experiments:read` |
| `POST` | `/api/v1/models/{model_id}/promote` | Promote a model to production | required | `models:promote` |
| `POST` | `/api/v1/models/rollback` | Roll back to the previously active model | required | `models:promote` |
| `GET` | `/api/v1/experiments` | Experiments | required | `experiments:read` |
| `POST` | `/api/v1/experiments` | Register an experiment configuration | required | `experiments:write` |
| `GET` | `/api/v1/experiments/{eid}` | Experiment detail | required | `experiments:read` |
| `POST` | `/api/v1/experiments/{eid}/run` | Queue a training run (background job) | required | `experiments:write` |
| `POST` | `/api/v1/evaluation/runs` | Evaluate the active model on a dataset version (e.g. new signers) | required | `experiments:write` |
| `GET` | `/api/v1/evaluation/runs` | Evaluation runs on dataset versions | required | `experiments:read` |
| `GET` | `/api/v1/evaluation/runs/{rid}` | Evaluation run detail with per-recording rows | required | `experiments:read` |

## practice

| Method | Path | Summary | Auth | Permission |
|---|---|---|---|---|
| `GET` | `/api/v1/practice/status` | Whether practice reference data is installed | optional | - |
| `GET` | `/api/v1/practice/reference/{sign_id}` | Reference landmark sequence of a sign for animation | optional | - |
| `POST` | `/api/v1/practice/score` | Score a practice attempt against the sign's reference | optional | - |

## personal

| Method | Path | Summary | Auth | Permission |
|---|---|---|---|---|
| `GET` | `/api/v1/history` | My recognition history | required | - |
| `POST` | `/api/v1/history` | Save a recognition result | required | - |
| `DELETE` | `/api/v1/history` | Clear my history | required | - |
| `PATCH` | `/api/v1/history/{hid}` | Correct a saved result | required | - |
| `DELETE` | `/api/v1/history/{hid}` | Delete one history item | required | - |
| `POST` | `/api/v1/feedback` | Send feedback or a correction report | optional | - |
| `GET` | `/api/v1/feedback` | Feedback inbox | required | `feedback:read` |
| `PATCH` | `/api/v1/feedback/{fid}` | Resolve feedback | required | `feedback:read` |
| `GET` | `/api/v1/learning/lessons` | Lessons by category (verified content by default) | optional | - |
| `GET` | `/api/v1/learning/quiz` | Quiz built only from verified signs and verified meanings | optional | - |
| `GET` | `/api/v1/learning/progress` | My learning progress | required | - |
| `GET` | `/api/v1/learning/achievements` | My streaks, points, weekly goal and badges (from my own attempts) | required | - |
| `POST` | `/api/v1/learning/attempts` | Record a practice or quiz attempt | required | - |
| `GET` | `/api/v1/phrases` | My saved phrases and the curated quick phrases | optional | - |
| `POST` | `/api/v1/phrases` | Save a composed phrase | required | - |
| `DELETE` | `/api/v1/phrases/{pid}` | Delete a phrase | required | - |
| `POST` | `/api/v1/analysis/videos` | Upload a video for analysis (auto-deleted after retention window) | required | - |
| `GET` | `/api/v1/analysis/videos` | My analysis jobs | required | - |
| `GET` | `/api/v1/analysis/videos/{jid}` | Analysis result | required | - |
| `DELETE` | `/api/v1/analysis/videos/{jid}` | Delete an analysis job and its video now | required | - |
| `GET` | `/api/v1/dashboard` | Aggregated dashboard data (real counts only) | optional | - |

## Prediction states

`POST /predict/sequence` returns `state` ∈ `recognized`, `uncertain`, `unknown`, `insufficient_input`, `model_unavailable` (the client adds `camera_unavailable`). `top` is empty unless a real model is loaded.
