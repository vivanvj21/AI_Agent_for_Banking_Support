"""
Pytest configuration & session setup.

Sets default test environment variables (ENV=testing, PERIMETER_AUTH_OPT_OUT=true)
so that running pytest out-of-the-box in test environment uses explicit opt-out.
Individual unit tests can override monkeypatch settings as needed.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("ENV", "testing")
os.environ.setdefault("PERIMETER_AUTH_OPT_OUT", "true")


@pytest.fixture(scope="session", autouse=True)
def initialize_test_database():
    """Ensure database schema and demo seed data are initialized for pytest session."""
    from db.init_db import ensure_database
    from memory.store import ensure_memory_schema

    ensure_database(seed_demo_data=True)
    ensure_memory_schema()
