"""Shared pytest fixtures."""

import os
import sys

import pytest

# Ensure project root is on the path and env vars are set before any import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("WTF_CSRF_ENABLED", "false")


@pytest.fixture(scope="session")
def flask_app(tmp_path_factory):
    # Redirect DB_PATH to a throwaway file BEFORE importing app: app.py calls
    # db.init_db() at import time, which would otherwise run schema
    # initialization against the real data/patient_data.db on every test run.
    import src.db.connection as conn_mod
    conn_mod.DB_PATH = tmp_path_factory.mktemp("session-db") / "test.db"

    import app as application
    application.app.config["TESTING"] = True
    application.app.config["WTF_CSRF_ENABLED"] = False
    application.app.config["SERVER_NAME"] = "localhost"
    application.app.config["RATELIMIT_ENABLED"] = False
    if application.limiter is not None:
        application.limiter.enabled = False
    return application.app


@pytest.fixture
def client(flask_app):
    with flask_app.test_client() as c:
        yield c


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Isolated database for tests that touch the DB layer."""
    import src.db.connection as conn_mod
    test_path = tmp_path / "test.db"
    monkeypatch.setattr(conn_mod, "DB_PATH", test_path)
    conn_mod.init_db()
    yield test_path
