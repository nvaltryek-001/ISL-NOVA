# Repository audit

**Repository:** https://github.com/nvaltryek-001/ISL-NOVA (git remote resolves to `https://github.com/nvaltryek-001/isl-nova`)
**Audit date:** 2026-11-03
**Auditor:** Claude (AI coding agent) acting on the owner's instruction

## Findings at audit time

| Item | Observed |
|---|---|
| Commits | none: `git clone` reported *"You appear to have cloned an empty repository"* |
| Branches / tags | none |
| Default branch | not set (empty repository) |
| Files, README, workflows | none |
| Existing stack / legacy assets | none |
| Risks | none inherited; greenfield build |

## Actions taken

1. Created `main` with a single initial commit (minimal README and `.gitignore`) so the repository has a default branch. No later work is committed to `main`.
2. Created the development branch **`feat/isl-nova-platform`**; all implementation is committed there in milestone-sized commits.
3. No force pushes, no history rewriting.

## Build-environment constraints (recorded for reproducibility)

The implementation was produced in an isolated cloud sandbox with these limits. They explain several technology choices documented in [TECH_STACK.md](TECH_STACK.md).

| Constraint | Effect | Mitigation |
|---|---|---|
| PyPI and npm registries unreachable | FastAPI, SQLAlchemy, Alembic, Vite, TanStack Query, React Router, Zustand, Recharts, Framer Motion, Vitest, PyTorch and TensorFlow could not be installed | Built on the pre-installed, fully testable equivalents: Starlette + Pydantic (FastAPI's own foundation), hand-written versioned SQL migrations, esbuild + Tailwind v4, small in-house router/query/store modules, NumPy models |
| Zenodo, Kaggle and Hugging Face unreachable | No dataset could be downloaded | Vocabulary built from the INCLUDE label map and official split lists (in its MIT-licensed GitHub repo); an importer is provided for the 56.8 GB video release |
| Docker Hub / GHCR unreachable | Images could not be built | Dockerfile, Compose and CI written; container file layout and production start command verified outside Docker; image build runs in GitHub Actions |
| No PostgreSQL Python driver | API could not run against PostgreSQL locally | Schema applied to a real PostgreSQL 16 server with `psql`; all 163 distinct SQL statements executed by the test suite were type-checked on it with `PREPARE`; the full suite runs on PostgreSQL in CI |
| MediaPipe CDN / model files unreachable | In-browser and server landmark extraction could not run | Extraction code is written against the MediaPipe Tasks API; E2E tests verify the honest *extractor unavailable* state |
| `gh` CLI token invalid | Pull request could not be opened from the sandbox | Branch pushed with git; PR to be opened from GitHub |
