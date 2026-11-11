"""Administrative CLI.

    python -m app.manage create-user --email a@b.org --name "Asha" --role admin --role linguist
    python -m app.manage seed            # migrate + roles + vocabulary
    python -m app.manage retention [--apply]   # data-retention job (dry run by default)
    python -m app.manage set-password --email admin@example.org   # new password; signs out all sessions
    python -m app.manage list-users
"""

from __future__ import annotations

import argparse
import getpass
import json
import os

from .config import Settings
from .db import Database
from .migrate import migrate
from .security import MIN_PASSWORD, ROLES, hash_password
from .services import ensure_user, make_storage, seed_roles, seed_vocabulary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    cu = sub.add_parser("create-user")
    cu.add_argument("--email", required=True)
    cu.add_argument("--name", required=True)
    cu.add_argument("--role", action="append", choices=sorted(ROLES), default=[])
    sub.add_parser("seed")
    sp = sub.add_parser("set-password")
    sp.add_argument("--email", required=True)
    sub.add_parser("list-users")
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
        if a.cmd == "list-users":
            for u in c.all("SELECT u.id, u.email, u.display_name FROM users u ORDER BY u.id"):
                roles = [r["role_name"] for r in c.all("SELECT role_name FROM user_roles WHERE user_id = ?", (u["id"],))]
                print(f"{u['id']:>4}  {u['email']:<40} {u['display_name']}  [{', '.join(roles)}]")
            return 0
        if a.cmd == "set-password":
            row = c.one("SELECT id FROM users WHERE email = ?", (a.email.lower(),))
            if not row:
                raise SystemExit(f"no user with email {a.email}; see: python -m app.manage list-users")
            pw = os.environ.get("ISL_NOVA_NEW_PASSWORD") or getpass.getpass("New password: ")
            if not os.environ.get("ISL_NOVA_NEW_PASSWORD") and pw != getpass.getpass("Repeat new password: "):
                raise SystemExit("passwords do not match")
            if len(pw) < MIN_PASSWORD:
                raise SystemExit(f"password must be at least {MIN_PASSWORD} characters")
            c.execute("UPDATE users SET password_hash = ?, token_version = token_version + 1 WHERE id = ?",
                      (hash_password(pw, s.pbkdf2_iterations), row["id"]))
            print({"user_id": row["id"], "password_changed": True, "other_sessions_signed_out": True})
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
