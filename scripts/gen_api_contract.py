#!/usr/bin/env python3
"""Regenerate docs/API_CONTRACT.md from the application's own OpenAPI spec.

    PYTHONPATH=backend:ml python scripts/gen_api_contract.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "ml")]

from app.api import openapi  # noqa: E402
from app.main import ROUTERS  # noqa: E402


def main() -> None:
    spec = openapi(ROUTERS)
    lines = [
        "# API contract",
        "",
        "Generated from the application's OpenAPI document by `scripts/gen_api_contract.py`, "
        "so it always matches the code. The machine-readable spec is served at `/api/v1/openapi.json` "
        "and an interactive viewer at `/api/docs`.",
        "",
        "* Base path: `/api/v1`. JSON in and out (multipart for uploads).",
        "* Auth: `Authorization: Bearer <JWT>` from `POST /auth/login` or `/auth/register`.",
        '* Errors: `{"error": {"code", "message", "details?"}}` with 401 / 403 / 404 / 409 / 413 / 415 / 422 / 429.',
        "* **Auth** column: `public`, `optional` (works anonymously, richer when signed in) or `required`. "
        "**Permission** is enforced server-side.",
        "",
    ]
    by_tag: dict[str, list] = {}
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            by_tag.setdefault(op["tags"][0], []).append((path, method.upper(), op))
    for tag, ops in by_tag.items():
        lines += [f"## {tag}", "", "| Method | Path | Summary | Auth | Permission |", "|---|---|---|---|---|"]
        for path, method, op in ops:
            sec = op.get("security")
            auth = "public" if sec is None else "optional" if {} in sec else "required"
            perm = op.get("description", "").replace("Requires permission ", "").rstrip(".") or "-"
            lines.append(f"| `{method}` | `{path}` | {op['summary']} | {auth} | {perm} |")
        lines.append("")
    lines += ["## Prediction states", "",
              "`POST /predict/sequence` returns `state` ∈ `recognized`, `uncertain`, `unknown`, "
              "`insufficient_input`, `model_unavailable` (the client adds `camera_unavailable`). "
              "`top` is empty unless a real model is loaded.", ""]
    out = ROOT / "docs" / "API_CONTRACT.md"
    out.write_text("\n".join(lines))
    print(f"wrote {out} ({sum(len(v) for v in by_tag.values())} operations)")


if __name__ == "__main__":
    main()
