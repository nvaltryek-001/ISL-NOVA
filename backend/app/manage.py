"""Administrative CLI.

    python -m app.manage create-user --email a@b.org --name "Asha" --role admin --role linguist
    python -m app.manage seed            # migrate + roles + vocabulary
    python -m app.manage retention [--apply]   # data-retention job (dry run by default)
"""

from __future__ import annotations

import argparse
import getpass
import json
import os

from .config import Settings
from .db import Database
from .migrate import migrate
from .security import MIN_PASSWORD, ROLES
from .services import ensure_user, make_storage, seed_roles, seed_vocabulary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    cu = sub.add_parser("create-user")
    cu.add_argument("--email", required=True)
    cu.add_argument("--name", required=True)
    cu.add_argument("--role", action="append", choices=sorted(ROLES), default=[])
    sub.add_parser("seed")
    rt = sub.add_parser("retention")
    rt.add_argument("--apply", action="store_true", help="delete (default: dry run)")
    a = ap.parse_args(argv)
    s = Settings.from_env()
    db = Database(s.database_url)
    migrate(db)
    with db.connect() as c:
        seed_roles(c)
        if a.cmd == "retention":
            from .retention import run_retention
            print(json.dumps(run_retention(c, s, make_storage(s), apply=a.apply), indent=1))
            return 0
        if a.cmd == "seed":
            print({"vocabulary_added": seed_vocabulary(c, s.vocab_dir)})
            return 0
        pw = os.environ.get("ISL_NOVA_NEW_PASSWORD") or getpass.getpass("Password: ")
        if len(pw) < MIN_PASSWORD:
            raise SystemExit(f"password must be at least {MIN_PASSWORD} characters")
        uid = ensure_user(c, a.email, pw, a.name, a.role or ["learner"], s.pbkdf2_iterations)
        print({"user_id": uid, "roles": a.role or ["learner"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
