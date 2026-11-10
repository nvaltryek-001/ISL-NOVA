"""Thin database layer supporting SQLite (dev/test) and PostgreSQL (production).

SQL is written with ``?`` placeholders; they are rewritten to ``%s`` for
psycopg. Rows are returned as plain dicts with timestamps normalised to ISO-8601
UTC strings so the API layer behaves identically on both engines.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any


def utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def jload(v: Any) -> Any:
    if v is None or isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        return v


def jdump(v: Any) -> str | None:
    return None if v is None else json.dumps(v)


def _norm_value(v: Any) -> Any:
    if isinstance(v, Decimal):  # PostgreSQL SUM()/AVG() return numeric
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=UTC)
        return v.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return v


class Database:
    def __init__(self, url: str):
        self.url = url
        if url.startswith("sqlite:///"):
            self.dialect = "sqlite"
            self.path = url[len("sqlite:///"):]
            if self.path != ":memory:":
                Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            self._mem_lock = threading.RLock()
            self._mem_conn: sqlite3.Connection | None = None
        elif url.startswith(("postgresql://", "postgres://")):
            self.dialect = "postgresql"
            try:
                import psycopg  # noqa: F401
            except ImportError as exc:  # pragma: no cover - depends on deployment
                raise RuntimeError("PostgreSQL requires the 'psycopg' package (see backend/requirements.txt)") from exc
        else:
            raise ValueError("DATABASE_URL must start with sqlite:/// or postgresql://")

    # -- connections ------------------------------------------------------
    def _connect_sqlite(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL")
        return conn

    @contextmanager
    def connect(self) -> Iterator[Conn]:
        if self.dialect == "sqlite":
            if self.path == ":memory:":
                with self._mem_lock:
                    if self._mem_conn is None:
                        self._mem_conn = self._connect_sqlite()
                    yield Conn(self._mem_conn, "sqlite")
                return
            raw = self._connect_sqlite()
            try:
                yield Conn(raw, "sqlite")
            finally:
                raw.close()
        else:  # pragma: no cover - exercised only with a PostgreSQL deployment
            import psycopg
            from psycopg.rows import dict_row

            with psycopg.connect(self.url, row_factory=dict_row, autocommit=True) as raw:
                yield Conn(raw, "postgresql")


class Conn:
    def __init__(self, raw, dialect: str):
        self.raw, self.dialect = raw, dialect
        self._depth = 0

    def _sql(self, sql: str) -> str:
        return sql.replace("?", "%s") if self.dialect == "postgresql" else sql

    def execute(self, sql: str, params: tuple | list = ()):
        return self.raw.execute(self._sql(sql), tuple(params))

    def all(self, sql: str, params: tuple | list = ()) -> list[dict]:
        cur = self.execute(sql, params)
        return [{k: _norm_value(r[k]) for k in r.keys()} for r in cur.fetchall()]

    def one(self, sql: str, params: tuple | list = ()) -> dict | None:
        rows = self.all(sql, params)
        return rows[0] if rows else None

    def scalar(self, sql: str, params: tuple | list = ()) -> Any:
        r = self.one(sql, params)
        return None if r is None else next(iter(r.values()))

    def insert(self, table: str, values: dict, pk: str | None = "id") -> Any:
        cols = ", ".join(values)
        qs = ", ".join("?" for _ in values)
        sql = f"INSERT INTO {table} ({cols}) VALUES ({qs})"
        if pk:
            sql += f" RETURNING {pk}"
            return self.scalar(sql, list(values.values()))
        self.execute(sql, list(values.values()))
        return None

    def update(self, table: str, values: dict, where: str, params: tuple | list) -> int:
        if not values:
            return 0
        sets = ", ".join(f"{k} = ?" for k in values)
        cur = self.execute(f"UPDATE {table} SET {sets} WHERE {where}", [*values.values(), *params])
        return cur.rowcount

    @contextmanager
    def transaction(self) -> Iterator[Conn]:
        if self._depth:
            self._depth += 1
            try:
                yield self
            finally:
                self._depth -= 1
            return
        self._depth = 1
        self.execute("BEGIN")
        try:
            yield self
            self.execute("COMMIT")
        except BaseException:
            self.execute("ROLLBACK")
            raise
        finally:
            self._depth = 0
