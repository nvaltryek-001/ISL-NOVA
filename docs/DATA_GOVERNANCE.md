# Data governance

## Principles
1. **Consent before capture.** The server refuses uploads unless the signer has an active, unexpired consent that includes `recording_storage`.
2. **Purpose limitation.** Training uses only recordings whose consent includes `model_training`, checked when a dataset version is frozen and again by the training pipeline.
3. **Minimisation.** Signers are pseudonymous codes. No names, contact details or face crops are stored. Live recognition sends landmarks, never video.
4. **Withdrawal is erasure.** Revoking consent deletes the signer's media and landmark files from storage and tombstones the rows. Erasing a signer removes everything; if the signer appears in a frozen version, the rows are kept as tombstones so lineage stays intact, but the media is gone.
5. **Four-eyes review.** Annotators cannot approve their own annotations.
6. **No fabricated data.** Synthetic fixtures exist only for code tests. They use class IDs `SYN01…`, are flagged `synthetic: true` in every artefact, cannot be mixed with real data, and the registry refuses to promote them in production.
7. **Traceable lineage.** model → experiment → dataset version → manifest (SHA-256) → recording IDs → signer/session codes.

## Roles

| Role | Can |
|---|---|
| `learner` | Use recognition, learning, communication; own history, bookmarks, phrases |
| `linguist` | Edit vocabulary; **verify** signs and translations; review annotations; view recording media (audited) |
| `data_curator` | Manage signers, consent, sessions, recordings, annotations, dataset versions |
| `researcher` | Create and run experiments; read evaluation |
| `admin` | Everything, including model promotion and user management |

## Retention
* Analysis uploads (Video Analysis) are deleted after `ANALYSIS_RETENTION_HOURS` (default 24) or on demand.
* **Retention job** (`backend/app/retention.py`): runs at start-up and every `RETENTION_INTERVAL_HOURS` (default 24; 0 disables), and on demand with `python -m app.manage retention [--apply]` (dry run by default) or `POST /api/v1/admin/retention`. It deletes used/expired password-reset codes, read notifications older than `NOTIFICATION_RETENTION_DAYS` (180), recognition history older than `HISTORY_RETENTION_DAYS` (0 = never) and expired analysis files. **Dataset recordings are never deleted automatically**: recordings past their consent retention date are listed under `needs_review` for a data curator, who deletes them through the erasure workflow.
* Recordings follow the signer's `retention_until` (validation should flag expired consent; automated purge is on the roadmap).
* Audit logs are kept for accountability; they contain actions and identifiers, not media.

## Audit events
`auth.*`, `sign.*`, `translation.set`, `signer.*`, `consent.grant|revoke`, `recording.upload|delete|view_media`, `annotation.*`, `dataset.validate|version_create`, `experiment.*`, `model.promote|rollback`, `admin.user_updated`, `feedback.update`.
