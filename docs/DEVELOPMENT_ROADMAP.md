# Development roadmap

| Milestone | Scope | Status |
|---|---|---|
| M0 Audit & setup | repository audit, branch, docs, CI | ✅ done |
| M1 Engineering foundation | API framework, migrations, config, logging, Docker, tests | ✅ done (Docker image build pending CI) |
| M2 Core application | shell, auth/RBAC, dashboard, vocabulary CRUD/search | ✅ done |
| M3 200-class dataset | 200 IDs, verification workflow, source audit, recording studio, consent, annotation, validation, manifests, readiness | ✅ software done · ⏳ **linguistic review and data collection outstanding** |
| M4 Computer vision | feature contract, browser + server extractors, parity tests | ✅ done · ⏳ extractor not run against real video in the sandbox |
| M5 AI/ML | loaders, signer split, LSTM baseline, GRU, logistic regression, DTW, calibration, evaluation, registry | ✅ code + synthetic smoke test · ⛔ **real training blocked on data** |
| M6 Live recognition | webcam, smoothing, states, meanings, speech, history, feedback | ✅ done · ⛔ inference untested with a real model |
| M7 Learning/communication | explorer, lessons, quiz, progress, composer, speech | ✅ done (content appears as signs are verified) |
| M8 Research/advanced | research centre, protocols, 3D viewer | ✅ done (results empty by design) |
| M9 Hardening | security controls, accessibility, responsive, E2E | ✅ done |
| M10 Delivery | README, screenshots, deployment guide, push | ✅ pushed · ⛔ PR/deploy need owner action |

## Next
1. **Owner:** import INCLUDE (56.8 GB) and run the importer; recruit qualified ISL reviewers for the `linguist` role.
2. Train the LSTM baseline on the INCLUDE official split; publish metrics in the model card with the signer-ID caveat.
3. Collect consented recordings from ≥ 10 signers for a true signer-independent test set.
4. Add PyTorch TCN and Temporal-Transformer candidates; ablations per [research/ABLATION_STUDY.md](../research/ABLATION_STUDY.md).
5. S3 storage adapter, scheduled retention purge, Redis rate limiting, refresh tokens.
6. Hindi/Kannada UI localisation (meanings are already multilingual).
