"""Tests for the database layer — uses an isolated temp database."""

import pytest
from werkzeug.security import generate_password_hash


# --- execute_many rollback ---

def test_execute_many_rolls_back_on_failure(temp_db):
    from src.db.connection import execute_many, fetch_one

    # Insert a user successfully first
    execute_many([
        ("INSERT INTO users (username, password_hash) VALUES (?, ?)", ("alice", "hash1")),
    ])
    assert fetch_one("SELECT username FROM users WHERE username = ?", ("alice",)) is not None

    # Second batch: first statement is valid, second violates UNIQUE on username
    with pytest.raises(Exception):
        execute_many([
            ("INSERT INTO users (username, password_hash) VALUES (?, ?)", ("bob", "hash2")),
            ("INSERT INTO users (username, password_hash) VALUES (?, ?)", ("alice", "hash3")),  # duplicate
        ])

    # bob must not exist — the whole batch was rolled back
    assert fetch_one("SELECT username FROM users WHERE username = ?", ("bob",)) is None


# --- user CRUD ---

def test_create_and_fetch_user(temp_db):
    from src.db.users import create_user, get_user_by_username

    create_user("testuser", generate_password_hash("password123"))
    user = get_user_by_username("testuser")
    assert user is not None
    assert user["username"] == "testuser"

def test_get_nonexistent_user_returns_none(temp_db):
    from src.db.users import get_user_by_username
    assert get_user_by_username("nobody") is None


# --- login lockout ---

def test_account_lockout_after_max_attempts(temp_db):
    from src.db.users import create_user, record_failed_login, is_account_locked

    create_user("lockeduser", generate_password_hash("pw"))
    assert not is_account_locked("lockeduser")

    for _ in range(5):
        result = record_failed_login("lockeduser", max_attempts=5, lock_minutes=15)

    assert result["locked"] is True
    assert is_account_locked("lockeduser")

def test_successful_login_clears_lockout(temp_db):
    from src.db.users import create_user, record_failed_login, record_successful_login, is_account_locked

    create_user("cleareduser", generate_password_hash("pw"))
    for _ in range(5):
        record_failed_login("cleareduser", max_attempts=5)

    assert is_account_locked("cleareduser")
    record_successful_login("cleareduser")
    assert not is_account_locked("cleareduser")


# --- roles ---

def test_assign_and_check_role(temp_db):
    from src.db.users import create_user, assign_role, has_any_role, get_user_roles

    create_user("radiologist1", generate_password_hash("pw"))
    assign_role("radiologist1", "radiologist", "admin")

    assert has_any_role("radiologist1", ["radiologist"])
    assert not has_any_role("radiologist1", ["admin"])
    assert "radiologist" in get_user_roles("radiologist1")

def test_remove_role(temp_db):
    from src.db.users import create_user, assign_role, remove_role, has_any_role

    create_user("tempuser", generate_password_hash("pw"))
    assign_role("tempuser", "admin")
    assert has_any_role("tempuser", ["admin"])

    remove_role("tempuser", "admin")
    assert not has_any_role("tempuser", ["admin"])

def test_has_any_role_empty_inputs(temp_db):
    from src.db.users import has_any_role
    assert not has_any_role("", ["admin"])
    assert not has_any_role("anyone", [])


# --- MFA ---

def test_totp_enable_disable(temp_db):
    from src.db.users import create_user, set_totp_secret, enable_totp, disable_totp, is_totp_enabled, get_totp_secret

    create_user("mfauser", generate_password_hash("pw"))
    assert not is_totp_enabled("mfauser")
    assert get_totp_secret("mfauser") is None

    set_totp_secret("mfauser", "JBSWY3DPEHPK3PXP")
    enable_totp("mfauser")
    assert is_totp_enabled("mfauser")
    assert get_totp_secret("mfauser") == "JBSWY3DPEHPK3PXP"

    disable_totp("mfauser")
    assert not is_totp_enabled("mfauser")
    assert get_totp_secret("mfauser") is None
