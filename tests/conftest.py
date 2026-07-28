"""
Pytest configuration & session setup.

Sets default test environment variables (ENV=testing, PERIMETER_AUTH_OPT_OUT=true)
so that running pytest out-of-the-box in test environment uses explicit opt-out.
Individual unit tests can override monkeypatch settings as needed.
"""

import os

os.environ.setdefault("ENV", "testing")
os.environ.setdefault("PERIMETER_AUTH_OPT_OUT", "true")
