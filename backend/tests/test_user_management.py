"""Tests for user management: registration and password change."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir(parents=True, exist_ok=True)
    (frontend_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    return TestClient(create_app(frontend_dir=frontend_dir, db_path=tmp_path / "pm.db"))


# ===== Registration =====


def test_register_creates_new_user(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.post(
        "/api/auth/register",
        json={"username": "newuser", "password": "secure123"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["username"] == "newuser"


def test_register_logs_in_automatically(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    client.post("/api/auth/register", json={"username": "autouser", "password": "pass123"})
    me_response = client.get("/api/auth/me")

    assert me_response.status_code == 200
    assert me_response.json()["username"] == "autouser"


def test_register_creates_default_board(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    client.post("/api/auth/register", json={"username": "boarduser", "password": "pass123"})

    boards = client.get("/api/boards").json()["boards"]
    assert len(boards) == 1
    assert boards[0]["name"] == "Project Board"


def test_register_duplicate_username_returns_409(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    client.post("/api/auth/register", json={"username": "dupuser", "password": "pass123"})
    client.post("/api/auth/logout")

    response = client.post(
        "/api/auth/register",
        json={"username": "dupuser", "password": "otherpass"},
    )

    assert response.status_code == 409
    assert "already taken" in response.json()["detail"].lower()


def test_register_duplicate_mvp_username_returns_409(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.post(
        "/api/auth/register",
        json={"username": "user", "password": "newpassword"},
    )

    assert response.status_code == 409


def test_register_empty_username_rejected(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.post("/api/auth/register", json={"username": "", "password": "pass123"})
    assert response.status_code == 422

    response = client.post("/api/auth/register", json={"username": "   ", "password": "pass123"})
    assert response.status_code == 422


def test_register_short_password_rejected(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    # Passwords must be at least 6 characters.
    response = client.post("/api/auth/register", json={"username": "shortpass", "password": "ab"})
    assert response.status_code == 422


def test_registered_user_can_login(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    client.post("/api/auth/register", json={"username": "loginuser", "password": "mypassword"})
    client.post("/api/auth/logout")

    login_response = client.post(
        "/api/auth/login",
        json={"username": "loginuser", "password": "mypassword"},
    )
    assert login_response.status_code == 200

    me_response = client.get("/api/auth/me")
    assert me_response.json()["username"] == "loginuser"


# ===== Password change =====


def test_change_password_success(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client.post("/api/auth/login", json={"username": "user", "password": "password"})

    response = client.patch(
        "/api/auth/password",
        json={"current_password": "password", "new_password": "newpassword"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_change_password_allows_login_with_new_password(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client.post("/api/auth/login", json={"username": "user", "password": "password"})

    client.patch(
        "/api/auth/password",
        json={"current_password": "password", "new_password": "updated123"},
    )
    client.post("/api/auth/logout")

    login_response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "updated123"},
    )
    assert login_response.status_code == 200


def test_change_password_rejects_old_password(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client.post("/api/auth/login", json={"username": "user", "password": "password"})

    client.patch(
        "/api/auth/password",
        json={"current_password": "password", "new_password": "updated123"},
    )
    client.post("/api/auth/logout")

    # Old password must not work anymore.
    login_response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    assert login_response.status_code == 401


def test_change_password_wrong_current_password_returns_401(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client.post("/api/auth/login", json={"username": "user", "password": "password"})

    response = client.patch(
        "/api/auth/password",
        json={"current_password": "wrongpassword", "new_password": "newpass123"},
    )
    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"].lower()


def test_change_password_requires_authentication(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.patch(
        "/api/auth/password",
        json={"current_password": "password", "new_password": "newpass123"},
    )
    assert response.status_code == 401


def test_change_password_short_new_password_rejected(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client.post("/api/auth/login", json={"username": "user", "password": "password"})

    response = client.patch(
        "/api/auth/password",
        json={"current_password": "password", "new_password": "ab"},
    )
    assert response.status_code == 422


# ===== Multi-user isolation =====


def test_multiple_users_have_independent_boards(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    # User 1 adds a card.
    client.post("/api/auth/login", json={"username": "user", "password": "password"})
    client.post(
        "/api/cards",
        json={"columnId": "col-backlog", "title": "User1 Card", "details": ""},
    )
    client.post("/api/auth/logout")

    # User 2 registers and should not see User 1's card.
    client.post("/api/auth/register", json={"username": "user2", "password": "pass123"})
    board = client.get("/api/board").json()["board"]
    assert all(c["title"] != "User1 Card" for c in board["cards"].values())
