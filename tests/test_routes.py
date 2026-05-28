"""HTTP route tests using the Flask test client."""

import pytest
from werkzeug.security import generate_password_hash


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Each test gets a fresh database."""
    import src.db.connection as conn_mod
    test_path = tmp_path / "test.db"
    monkeypatch.setattr(conn_mod, "DB_PATH", test_path)
    conn_mod.init_db()
    yield


def _register_user(username: str, password: str) -> None:
    from src.db.users import create_user
    create_user(username, generate_password_hash(password))


# --- login ---

def test_login_success_redirects_to_dashboard(client):
    _register_user("alice", "StrongPass123!")
    resp = client.post("/login", data={"username": "alice", "password": "StrongPass123!"}, follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/dashboard" in resp.headers.get("Location", "")


def test_login_wrong_password_stays_on_login(client):
    _register_user("bob", "StrongPass123!")
    resp = client.post("/login", data={"username": "bob", "password": "wrong"}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Invalid username or password" in resp.data


def test_login_nonexistent_user(client):
    resp = client.post("/login", data={"username": "ghost", "password": "anything"}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Invalid username or password" in resp.data


def test_logout_clears_session(client):
    _register_user("carol", "StrongPass123!")
    client.post("/login", data={"username": "carol", "password": "StrongPass123!"})
    resp = client.get("/logout", follow_redirects=False)
    assert resp.status_code in (302, 303)

    # After logout, a login-required route should redirect to login
    resp2 = client.get("/profile", follow_redirects=False)
    assert resp2.status_code in (302, 303)


# --- protected routes redirect to login when not authenticated ---

@pytest.mark.parametrize("path", ["/profile", "/feedback-admin"])
def test_protected_route_redirects_unauthenticated(client, path):
    resp = client.get(path, follow_redirects=False)
    assert resp.status_code in (302, 303)
    location = resp.headers.get("Location", "")
    assert "login" in location


# --- RBAC: admin-only routes ---

def test_feedback_admin_requires_admin_role(client):
    _register_user("plainuser", "StrongPass123!")
    client.post("/login", data={"username": "plainuser", "password": "StrongPass123!"})
    resp = client.get("/feedback-admin", follow_redirects=True)
    # Should be denied (flash "Access denied") or redirect away
    assert b"Access denied" in resp.data or resp.status_code in (302, 303, 403)


def test_feedback_admin_accessible_with_admin_role(client):
    from src.db.users import assign_role
    _register_user("adminuser", "StrongPass123!")
    assign_role("adminuser", "admin")
    client.post("/login", data={"username": "adminuser", "password": "StrongPass123!"})
    resp = client.get("/feedback-admin", follow_redirects=True)
    assert resp.status_code == 200


# --- account lockout ---

def test_repeated_failed_logins_lock_account(client):
    _register_user("victim", "StrongPass123!")
    for _ in range(5):
        client.post("/login", data={"username": "victim", "password": "wrong"})

    resp = client.post("/login", data={"username": "victim", "password": "StrongPass123!"}, follow_redirects=True)
    assert b"locked" in resp.data.lower()


# --- report ownership ---

def test_report_detail_requires_login(client):
    resp = client.get("/reports/1", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "login" in resp.headers.get("Location", "")


def test_report_detail_blocks_other_user(client):
    from src.db.patients import add_patient_record
    _register_user("owner", "StrongPass123!")
    _register_user("stranger", "StrongPass123!")

    # Create a report belonging to "owner"
    report_id = add_patient_record({
        "name": "Test Patient", "age": "40", "sex": "M",
        "study": "CT Chest", "findings": "clear", "username": "owner",
    })

    # Log in as "stranger" and try to read owner's report
    client.post("/login", data={"username": "stranger", "password": "StrongPass123!"})
    resp = client.get(f"/reports/{report_id}", follow_redirects=False)
    assert resp.status_code == 403


def test_report_detail_allows_owner(client):
    from src.db.patients import add_patient_record
    _register_user("realowner", "StrongPass123!")

    report_id = add_patient_record({
        "name": "Test Patient", "age": "40", "sex": "F",
        "study": "MRI Brain", "findings": "normal", "username": "realowner",
    })

    client.post("/login", data={"username": "realowner", "password": "StrongPass123!"})
    resp = client.get(f"/reports/{report_id}", follow_redirects=True)
    assert resp.status_code == 200


# --- public routes are accessible without login ---

@pytest.mark.parametrize("path", ["/", "/login", "/signup", "/blogs"])
def test_public_routes_accessible(client, path):
    resp = client.get(path, follow_redirects=True)
    assert resp.status_code == 200
