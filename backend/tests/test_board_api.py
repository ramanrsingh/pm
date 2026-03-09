from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir(parents=True, exist_ok=True)
    (frontend_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    return TestClient(create_app(frontend_dir=frontend_dir, db_path=tmp_path / "pm.db"))


def login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    assert response.status_code == 200


def test_board_requires_authentication(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.get("/api/board")

    assert response.status_code == 401


def test_get_board_returns_seeded_data(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login(client)

    response = client.get("/api/board")

    assert response.status_code == 200
    board = response.json()["board"]
    assert len(board["columns"]) == 5
    assert "card-1" in board["cards"]


def test_rename_column_persists(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login(client)

    rename = client.patch("/api/columns/col-backlog", json={"title": "Ideas"})
    refresh = client.get("/api/board")

    assert rename.status_code == 200
    assert refresh.status_code == 200
    column = next(col for col in refresh.json()["board"]["columns"] if col["id"] == "col-backlog")
    assert column["title"] == "Ideas"


def test_rename_column_empty_title_rejected(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login(client)

    response = client.patch("/api/columns/col-backlog", json={"title": ""})
    assert response.status_code == 422

    response = client.patch("/api/columns/col-backlog", json={"title": "   "})
    assert response.status_code == 422


def test_create_card_whitespace_title_rejected(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login(client)

    response = client.post(
        "/api/cards",
        json={"columnId": "col-backlog", "title": "   ", "details": ""},
    )
    assert response.status_code == 422

    response = client.post(
        "/api/cards",
        json={"columnId": "col-backlog", "title": "", "details": ""},
    )
    assert response.status_code == 422


def test_card_lifecycle_create_edit_move_delete(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login(client)

    created = client.post(
        "/api/cards",
        json={"columnId": "col-backlog", "title": "New Task", "details": "Initial"},
    )
    assert created.status_code == 200

    board_after_create = created.json()["board"]
    created_card_id = next(
        card_id
        for card_id, card in board_after_create["cards"].items()
        if card["title"] == "New Task"
    )

    edited = client.patch(
        f"/api/cards/{created_card_id}",
        json={"title": "Updated Task", "details": "Updated"},
    )
    assert edited.status_code == 200
    assert edited.json()["board"]["cards"][created_card_id]["title"] == "Updated Task"

    moved = client.post(
        f"/api/cards/{created_card_id}/move",
        json={"columnId": "col-review", "position": 0},
    )
    assert moved.status_code == 200
    review_column = next(col for col in moved.json()["board"]["columns"] if col["id"] == "col-review")
    assert review_column["cardIds"][0] == created_card_id

    deleted = client.delete(f"/api/cards/{created_card_id}")
    assert deleted.status_code == 200
    assert created_card_id not in deleted.json()["board"]["cards"]


def test_move_card_to_missing_column_returns_404(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login(client)

    response = client.post(
        "/api/cards/card-1/move",
        json={"columnId": "col-does-not-exist", "position": 0},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Column not found."


def test_board_persists_across_app_recreation(tmp_path: Path) -> None:
    client_one = make_client(tmp_path)
    login(client_one)

    create_response = client_one.post(
        "/api/cards",
        json={"columnId": "col-done", "title": "Persist Me", "details": "Saved"},
    )
    assert create_response.status_code == 200

    client_two = make_client(tmp_path)
    login(client_two)
    board_response = client_two.get("/api/board")

    assert board_response.status_code == 200
    titles = [card["title"] for card in board_response.json()["board"]["cards"].values()]
    assert "Persist Me" in titles
