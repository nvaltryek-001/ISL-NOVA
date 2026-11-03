"""Versioned SQL migrations (``app/migrations/NNNN_name.sql``).

    python -m app.migrate            # apply pending migrations
    python -m app.migrate --status   # list applied / pending
    python -m app.migrate --render postgresql > schema.sql   # print expanded SQL

Each migration is applied once, inside a transaction, and its SHA-256 is
recorded; editing an applied migration is detected and refused.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

from .db import Conn, Database, utcnow

MIGRATIONS = Path(__file__).parent / "migrations"

TOKENS = {
    "sqlite": {"PK": "INTEGER PRIMARY KEY AUTOINCREMENT", "TS": "TEXT", "JSON": "TEXT",
               "BOOL": "INTEGER", "TRUE": "1", "FALSE": "0"},
    "postgresql": {"PK": "BIGSERIAL PRIMARY KEY", "TS": "TIMESTAMPTZ", "JSON": "JSONB",
                   "BOOL": "BOOLEAN", "TRUE": "TRUE", "FALSE": "FALSE"},
}


class MigrationError(RuntimeError):
    pass


def render(sql: str, dialect: str) -> str:
    return re.sub(r"\{\{(\w+)\}\}", lambda m: TOKENS[dialect][m.group(1)], sql)


def files() -> list[Path]:
    return sorted(p for p in MIGRATIONS.glob("[0-9][0-9][0-9][0-9]_*.sql"))


def _statements(sql: str) -> list[str]:
    body = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    return [s.strip() for s in body.split(";") if s.strip()]


def _ensure_table(c: Conn) -> None:
    c.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version VARCHAR(80) PRIMARY KEY, "
              "checksum VARCHAR(64) NOT NULL, applied_at VARCHAR(30) NOT NULL)")


def status(db: Database) -> dict:
    with db.connect() as c:
        _ensure_table(c)
        applied = {r["version"]: r["checksum"] for r in c.all("SELECT version, checksum FROM schema_migrations")}
    out = {"applied": [], "pending": [], "modified": []}
    for f in files():
        chk = hashlib.sha256(f.read_bytes()).hexdigest()
        if f.stem in applied:
            out["applied"].append(f.stem)
            if applied[f.stem] != chk:
                out["modified"].append(f.stem)
        else:
            out["pending"].append(f.stem)
    return out


def migrate(db: Database) -> list[str]:
    st = status(db)
    if st["modified"]:
        raise MigrationError(f"applied migrations were modified: {st['modified']}")
    done = []
    with db.connect() as c:
        for f in files():
            if f.stem not in st["pending"]:
                continue
            sql = render(f.read_text(), db.dialect)
            with c.transaction():
                for stmt in _statements(sql):
                    c.execute(stmt)
                c.insert("schema_migrations", {"version": f.stem,
                                                "checksum": hashlib.sha256(f.read_bytes()).hexdigest(),
                                                "applied_at": utcnow()}, pk=None)
            done.append(f.stem)
    return done


def main(argv=None) -> int:
    from .config import Settings

    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--render", choices=list(TOKENS))
    a = ap.parse_args(argv)
    if a.render:
        for f in files():
            sys.stdout.write(f"-- {f.name}\n{render(f.read_text(), a.render)}\n")
        return 0
    db = Database(Settings.from_env().database_url)
    if a.status:
        print(status(db))
        return 0
    print({"applied": migrate(db)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
