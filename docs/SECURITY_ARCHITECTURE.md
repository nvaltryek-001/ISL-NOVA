# Security architecture

| Control | Implementation | Tested by |
|---|---|---|
| Password storage | PBKDF2-HMAC-SHA256, 16-byte salt, 600k iterations (configurable), constant-time compare; dummy hash on unknown email to reduce timing oracle | `test_register_login_and_profile` |
| Sessions | JWT HS256 with `exp`/`sub`/`typ`/`tv`; deactivated users rejected on every request; 401 clears client session | `test_deactivated_user_cannot_use_token` |
| Revocation (v2) | **Sign out everywhere**: `tv` must equal `users.token_version`; `POST /auth/logout-all` bumps it, revoking every earlier token. Password reset bumps it too | `test_logout_all_revokes_every_session` + E2E |
| Password reset (v2) | Admin-issued one-time code (`secrets.token_urlsafe(24)`), only its SHA-256 stored, 30-minute expiry, single use, audit-logged; no email service needed | `test_admin_issued_password_reset` + E2E |
| Two-factor (v2) | Optional TOTP (RFC 6238, SHA-1, 6 digits, 30 s, ±1 step), standard library only; last used step stored to block replay; enabling and disabling need a valid code; an admin reset clears 2FA (lost-device recovery). Secrets are stored in the database unencrypted: protect database backups | `test_totp_rfc6238_vectors`, `test_two_factor_setup_login_and_disable` + E2E |
| Retention (v2) | Scheduled job deletes used/expired reset codes, old read notifications, optional old history and expired analysis files; never deletes dataset recordings automatically | `test_retention_job_dry_run_then_apply` |
| Metrics (v2) | `/metrics` only from localhost or with `METRICS_TOKEN`; no user data in labels | `test_prometheus_metrics` |
| Authorisation | Server-side permission map (`security.PERMISSIONS`) checked before every handler; extra rules (only linguists verify; no self-review; no self-demotion) | `test_rbac_on_sign_writes`, `test_verification_workflow_requires_linguist`, `test_recording_upload_validation_and_review_workflow` |
| Production guardrails | Startup fails without a ≥ 32-char `JWT_SECRET`, with wildcard CORS, or with synthetic models allowed | `test_production_settings_are_strict` |
| Input validation | Pydantic models for every body/query; landmark arrays shape-checked; 8 MB JSON cap | `test_prediction_without_model_is_honest` |
| Uploads | Size cap before read; magic-byte sniffing (ignores client MIME); full OpenCV decode; SHA-256 duplicate detection | upload tests |
| Path safety | Storage keys validated by regex and resolved inside the root | `test_storage_rejects_path_traversal` |
| Rate limiting | Sliding window per IP, stricter bucket for auth endpoints | `test_login_rate_limit` |
| CORS | Explicit origin allow-list, no credentials | `test_security_headers_and_cors` |
| Headers | CSP (self + pinned MediaPipe CDN), `X-Frame-Options: DENY`, `nosniff`, Referrer-Policy, Permissions-Policy (camera self only) | `test_security_headers_and_cors` |
| Media access | Recording media only to reviewers, `Cache-Control: no-store`, every view audited | upload test |
| Model integrity | Weights SHA-256 checked at load; contract version must match; npz loaded with `allow_pickle=False` | `test_predictor_rejects_tampered_weights` |
| Secrets | Only `.env.example` with placeholders committed; `.gitignore` excludes `.env*`, media, weights, data | pre-push scan |
| Logging | JSON logs without bodies, tokens or passwords; request IDs | - |

**Known gaps (roadmap):** the rate limiter is per process (use Redis behind multiple instances); there is no refresh-token rotation (sessions are short-lived access tokens plus sign-out-everywhere); TOTP secrets are not encrypted at rest; password reset needs an administrator (no email provider).
