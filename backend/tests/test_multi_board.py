"""Tests for multiple boards per user feature."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir(parents=True, exist_ok=True)
    (frontend_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    return TestClient(create_app(frontend_dir=frontend_dir, db_path=tmp_path / "pm.db"))


def login(client: TestClient, username: str = "user", password: str = "password") -> None:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200


# ===== List boards =====


def test_list_boards_requires_authentication(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/api/boards")
    assert response.status_code == 401


def test_list_boards_returns_default_board(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login(client)

    response = client.get("/api/boards")

    assert response.status_code == 200
    boards = response.json()["boards"]
    assert len(boards) == 1
    assert boards[0]["name"] == "Project Board"
    assert "id" in boards[0]
    assert "createdAt" in boards[0]


# ===== Create board =====


def test_create_board_returns_new_board(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login(client)

    response = client.post("/api/boards", json={"name": "Sprint 42"})

    assert response.status_code == 200
    board = response.json()["board"]
    assert board["name"] == "Sprint 42"
    assert len(board["columns"]) == 5
    assert board["cards"] == {}


def test_create_board_empty_name_rejected(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login(client)

    response = client.post("/api/boards", json={"name": ""})
    assert response.status_code == 422

    response = client.post("/api/boards", json={"name": "   "})
    assert response.status_code == 422


def test_create_multiple_boards_all_listed(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login(client)

    client.post("/api/boards", json={"name": "Board Alpha"})
    client.post("/api/boards", json={"name": "Board Beta"})

    response = client.get("/api/boards")
    boards = response.json()["boards"]
    names = [b["name"] for b in boards]
    assert "Project Board" in names
    assert "Board Alpha" in names
    assert "Board Beta" in names
    assert len(boards) == 3


# ===== Get board by id =====


def test_get_board_by_id(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login(client)

    create_resp = client.post("/api/boards", json={"name": "My New Board"})
    board_id = create_resp.json()["board"]["id"]

    response = client.get(f"/api/boards/{board_id}")

    assert response.status_code == 200
    assert response.json()["board"]["name"] == "My New Board"
    assert response.json()["board"]["id"] == board_id


def test_get_board_by_id_other_user_returns_404(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login(client)

    create_resp = client.post("/api/boards", json={"name": "Private Board"})
    board_id = create_resp.json()["board"]["id"]

    # Register and log in as a different user.
    client.post("/api/auth/logout")
    client.post("/api/auth/register", json={"username": "alice", "password": "securepass"})

    response = client.get(f"/api/boards/{board_id}")
    assert response.status_code == 404


def test_get_board_by_id_nonexistent_returns_404(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login(client)

    response = client.get("/api/boards/board-does-not-exist")
    assert response.status_code == 404


# ===== Rename board =====


def test_rename_board(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login(client)

    create_resp = client.post("/api/boards", json={"name": "Old Name"})
    board_id = create_resp.json()["board"]["id"]

    patch_resp = client.patch(f"/api/boards/{board_id}", json={"name": "New Name"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["board"]["name"] == "New Name"

    get_resp = client.get(f"/api/boards/{board_id}")
    assert get_resp.json()["board"]["name"] == "New Name"


# ===== Delete board =====


def test_delete_board_success(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login(client)

    create_resp = client.post("/api/boards", json={"name": "Disposable Board"})
    board_id = create_resp.json()["board"]["id"]

    delete_resp = client.delete(f"/api/boards/{board_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["status"] == "ok"

    get_resp = client.get(f"/api/boards/{board_id}")
    assert get_resp.status_code == 404


def test_delete_last_board_rejected(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login(client)

    boards = client.get("/api/boards").json()["boards"]
    assert len(boards) == 1
    board_id = boards[0]["id"]

    response = client.delete(f"/api/boards/{board_id}")
    assert response.status_code == 400
    assert "last board" in response.json()["detail"].lower()


def test_delete_board_other_user_returns_404(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login(client)

    create_resp = client.post("/api/boards", json={"name": "Board to protect"})
    board_id = create_resp.json()["board"]["id"]

    client.post("/api/auth/logout")
    client.post("/api/auth/register", json={"username": "bob", "password": "bobspass"})

    response = client.delete(f"/api/boards/{board_id}")
    assert response.status_code == 404


# ===== Board-scoped column management =====


def test_add_column_to_board(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login(client)

    boards = client.get("/api/boards").json()["boards"]
    board_id = boards[0]["id"]

    response = client.post(f"/api/boards/{board_id}/columns", json={"title": "Staging"})
    assert response.status_code == 200
    board = response.json()["board"]
    column_titles = [c["title"] for c in board["columns"]]
    assert "Staging" in column_titles


def test_add_column_empty_title_rejected(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login(client)

    boards = client.get("/api/boards").json()["boards"]
    board_id = boards[0]["id"]

    response = client.post(f"/api/boards/{board_id}/columns", json={"title": ""})
    assert response.status_code == 422


def test_rename_column_on_board(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login(client)

    board_resp = client.get("/api/boards").json()
    board_id = board_resp["boards"][0]["id"]

    board = client.get(f"/api/boards/{board_id}").json()["board"]
    column_id = board["columns"][0]["id"]

    patch_resp = client.patch(
        f"/api/boards/{board_id}/columns/{column_id}", json={"title": "Renamed"}
    )
    assert patch_resp.status_code == 200
    columns = patch_resp.json()["board"]["columns"]
    assert any(c["title"] == "Renamed" for c in columns)


def test_delete_column_removes_it_and_cards(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login(client)

    boards = client.get("/api/boards").json()["boards"]
    board_id = boards[0]["id"]

    # Add a new column and a card to it.
    add_col = client.post(f"/api/boards/{board_id}/columns", json={"title": "Temp"})
    new_col_id = next(
        c["id"] for c in add_col.json()["board"]["columns"] if c["title"] == "Temp"
    )

    client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": new_col_id, "title": "Temp Card", "details": ""},
    )

    del_resp = client.delete(f"/api/boards/{board_id}/columns/{new_col_id}")
    assert del_resp.status_code == 200
    board = del_resp.json()["board"]
    col_ids = [c["id"] for c in board["columns"]]
    assert new_col_id not in col_ids
    # Card in the deleted column should also be gone.
    assert all(card["title"] != "Temp Card" for card in board["cards"].values())


# ===== Board-scoped card management =====


def test_card_lifecycle_on_specific_board(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login(client)

    create_board_resp = client.post("/api/boards", json={"name": "Test Board"})
    board_id = create_board_resp.json()["board"]["id"]
    board = create_board_resp.json()["board"]
    backlog_col_id = board["columns"][0]["id"]
    review_col_id = board["columns"][3]["id"]

    # Create
    created = client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": backlog_col_id, "title": "Task X", "details": "details"},
    )
    assert created.status_code == 200
    card_id = next(
        cid for cid, c in created.json()["board"]["cards"].items() if c["title"] == "Task X"
    )

    # Update
    updated = client.patch(
        f"/api/boards/{board_id}/cards/{card_id}",
        json={"title": "Task X Updated"},
    )
    assert updated.status_code == 200
    assert updated.json()["board"]["cards"][card_id]["title"] == "Task X Updated"

    # Move
    moved = client.post(
        f"/api/boards/{board_id}/cards/{card_id}/move",
        json={"columnId": review_col_id, "position": 0},
    )
    assert moved.status_code == 200
    review_col = next(c for c in moved.json()["board"]["columns"] if c["id"] == review_col_id)
    assert card_id in review_col["cardIds"]

    # Delete
    deleted = client.delete(f"/api/boards/{board_id}/cards/{card_id}")
    assert deleted.status_code == 200
    assert card_id not in deleted.json()["board"]["cards"]


def test_board_scoped_card_ops_reject_wrong_board(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login(client)

    # Get default board and a card on it.
    default_board = client.get("/api/board").json()["board"]
    card_id = list(default_board["cards"].keys())[0]

    # Create a second board.
    second_board_resp = client.post("/api/boards", json={"name": "Second"})
    second_board_id = second_board_resp.json()["board"]["id"]

    # Try to update a card from the default board using the second board's route.
    response = client.patch(
        f"/api/boards/{second_board_id}/cards/{card_id}",
        json={"title": "Hacked"},
    )
    assert response.status_code == 404


# ===== Board data isolation between users =====


def test_boards_isolated_between_users(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    # Create card as default user.
    login(client)
    client.post("/api/cards", json={"columnId": "col-backlog", "title": "User card", "details": ""})
    client.post("/api/auth/logout")

    # Register new user and verify they see their own empty board.
    client.post("/api/auth/register", json={"username": "carol", "password": "carolpass"})
    board = client.get("/api/board").json()["board"]
    titles = [c["title"] for c in board["cards"].values()]
    assert "User card" not in titles
