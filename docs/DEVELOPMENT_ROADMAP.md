# Development roadmap

| Milestone | Scope | Status |
|---|---|---|
| M0 Audit & setup | repository audit, branch, docs, CI | ✅ done |
| M1 Engineering foundation | API framework, migrations, config, logging, Docker, tests | ✅ done (Docker image built and health-checked in CI) |
| M2 Core application | shell, auth/RBAC, dashboard, vocabulary CRUD/search | ✅ done |
| M3 200-class dataset | 200 IDs, verification workflow, source audit, recording studio, consent, annotation, validation, manifests, readiness | ✅ software done · ⏳ **linguistic review and data collection outstanding** |
| M4 Computer vision | feature contract, browser + server extractors, parity tests | ✅ done · server extractor run on all 4,284 INCLUDE videos in CI |
| M5 AI/ML | loaders, signer split, LSTM baseline, GRU, logistic regression, DTW, calibration, evaluation, registry | ✅ **trained on INCLUDE (200 classes, LSTM 91.7 % top-1)** · ⏳ signer-independent evaluation needs new data |
| M6 Live recognition | webcam, smoothing, states, meanings, speech, history, feedback | ✅ real model served via API and tested on held-out data · ⏳ real-camera, real-user test outstanding |
| M7 Learning/communication | explorer, lessons, quiz, progress, composer, speech | ✅ done (content appears as signs are verified) |
| M8 Research/advanced | research centre, protocols, 3D viewer | ✅ done (results empty by design) |
| M9 Hardening | security controls, accessibility, responsive, E2E | ✅ done |
| M10 Delivery | README, screenshots, deployment guide, push | ✅ pushed, PR #1 open · ⛔ deployment needs hosting credentials |

## Next
1. **Owner:** recruit qualified ISL reviewers for the `linguist` role and start verifying the 200 slots.
2. Test live webcam recognition with real signers (none of whom are in INCLUDE) and record the accuracy honestly.
3. Extract the 63 INCLUDE reserve glosses as held-out unknown classes to evaluate unknown-sign rejection; run ≥ 3 seeds.
4. Collect consented recordings from ≥ 10 signers for a true signer-independent test set.
5. Add PyTorch TCN and Temporal-Transformer candidates; ablations per [research/ABLATION_STUDY.md](../research/ABLATION_STUDY.md).
6. S3 storage adapter, scheduled retention purge, Redis rate limiting, refresh tokens.
7. Hindi/Kannada UI localisation (meanings are already multilingual).
