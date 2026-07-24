"""Centralized SQLite connection factory for the bank assistant.

All modules that need a database connection (tools/, db/) import
``get_connection`` from here instead of duplicating a ``_connect()``
helper.  This is the single place where:

* WAL mode is enabled (writes don't block readers; safe for the
  multi-handler FastAPI thread pool).
* ``foreign_keys`` enforcement is turned on.
* ``busy_timeout`` prevents immediate "database is locked" errors under
  brief write contention from the API server.
* ``cache_size`` is tuned for the workload size.

Nothing in this module performs schema creation or seeding — that
remains in db/init_db.py, which calls ``get_connection`` just like
every other module.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

LOGGER = logging.getLogger(__name__)

# Canonical path used by every module in the project.
DB_PATH = Path(__file__).parent / "bank.db"

# SQLite pragmas applied to every connection opened by this factory.
# Values are chosen for a single-file, moderate-concurrency web app.
_PRAGMAS = (
    ("journal_mode", "WAL"),  # allow concurrent readers during writes
    ("foreign_keys", "ON"),  # enforce FK constraints declared in schema.sql
    ("busy_timeout", "5000"),  # wait up to 5 s before raising OperationalError
    ("cache_size", "-8000"),  # 8 MB page cache (negative = kibibytes)
    ("synchronous", "NORMAL"),  # safe with WAL; faster than FULL
)


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with production-appropriate pragmas.

    Every call returns a *new* connection object (SQLite connections are
    not thread-safe to share).  Callers are responsible for closing the
    connection (use a ``try/finally`` block or ``with conn:``).

    Args:
        db_path: Override the database path. Defaults to ``DB_PATH``.
                 Pass a ``tmp_path`` from pytest fixtures for test isolation.

    Returns:
        A configured :class:`sqlite3.Connection` with ``row_factory`` set
        to :class:`sqlite3.Row` so columns are accessible by name.
    """
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row

    for pragma, value in _PRAGMAS:
        try:
            conn.execute(f"PRAGMA {pragma} = {value}")
        except sqlite3.OperationalError:
            # WAL is unsupported on some VFS (e.g. in-memory :memory: paths
            # used by certain test fixtures).  Log a warning but carry on —
            # the rest of the pragmas still apply.
            LOGGER.warning(
                "db_pragma_skipped",
                extra={"pragma": pragma, "db_path": str(path)},
            )

    return conn
