# Project blueprint

**ISL NOVA: Beyond Gestures. Towards Understanding.**

## Problem
Indian Sign Language (ISL) is used by a large Deaf community, but it has few openly licensed, consented datasets and few tools for learners or for everyday look-up. Many published "sign recognition" demos report accuracy on signers who also appear in the training data, which overstates real-world performance.

## Goals
1. A **traceable 200-class vocabulary** with explicit linguistic-verification and data-readiness state per class.
2. A **consent-first data pipeline** that lets communities contribute recordings safely.
3. A **reproducible recognition pipeline** evaluated signer-independently, with calibrated confidence and unknown-sign rejection.
4. **Useful, accessible applications**: live recognition, sign explorer, learning, communication and a kiosk, all honest about what the model can and cannot do.

## Non-goals (v1)
Continuous signing recognition; grammatical ISL ↔ text translation; facial/non-manual feature modelling; assessing a learner's signing quality.

## Users
Learners · Deaf and hearing communicators · ISL linguists and reviewers · data curators · ML researchers · administrators running kiosks.

## Modules
Core · Dashboard · Live Recognition Studio · Video Analysis · Sign Explorer · Communication Workspace · Learning Academy · Dataset Intelligence Lab · AI Laboratory · Research Centre · 3D Visualisation (experimental) · Admin & Kiosk. See [ARCHITECTURE.md](ARCHITECTURE.md) and [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

## Success criteria
A promoted model trained on approved, consented data; held-out (preferably signer-independent) macro-F1 and open-set AUROC published in the model card; verified vocabulary entries used in lessons, with Hindi and Kannada meanings checked by reviewers.
