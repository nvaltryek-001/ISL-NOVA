# Contributing

## Ground rules
* **Scientific integrity.** Never add invented signs, translations, recordings, metrics or citations. Leave unknown values blank or `TBD`.
* **ISL expertise.** Only qualified reviewers (Deaf signers or certified ISL professionals) should hold the `linguist` role.
* **Consent.** Never commit videos, landmarks, signer data or model weights.

## Setup
```bash
pip install -r backend/requirements-dev.txt
cd frontend && npm install && npm run build && cd ..
PYTHONPATH=backend:ml BOOTSTRAP_ADMIN_EMAIL=you@example.org BOOTSTRAP_ADMIN_PASSWORD='choose-a-long-one' \
  uvicorn app.main:app --app-dir backend --reload     # http://localhost:8000
cd frontend && npm run dev                            # rebuilds dist/ on change
```

## Checks (all must pass)
```bash
ruff check backend ml dataset/scripts
pytest -q                                   # backend + ML
cd frontend && npm run typecheck && npm test && npm run build && npm run e2e
```
Run the backend tests on PostgreSQL by setting `TEST_DATABASE_URL=postgresql://…`.

## Conventions
* Branch from `main` as `feat/…` or `fix/…`; Conventional Commit messages (`feat(api): …`, `test: …`).
* Schema changes: add a new `backend/app/migrations/NNNN_name.sql`; never edit an applied one.
* Feature changes: bump `CONTRACT_VERSION` and regenerate the parity fixture.
* API changes: run `python scripts/gen_api_contract.py`.
