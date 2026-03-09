from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir(parents=True, exist_ok=True)
    (frontend_dir / "index.html").write_text(
        "<html><body><h1>Kanban Studio</h1></body></html>",
        encoding="utf-8",
    )
    db_path = tmp_path / "pm.db"
    return TestClient(create_app(frontend_dir=frontend_dir, db_path=db_path))


def test_health_endpoint_returns_ok(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "pm-backend"}


def test_root_serves_frontend_index(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/")

    assert response.status_code == 200
    assert "Kanban Studio" in response.text


def test_api_still_works_when_frontend_static_is_mounted(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_login_rejects_invalid_credentials(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.post(
        "/api/auth/login",
        json={"username": "bad", "password": "creds"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password."


def test_login_sets_cookie_and_me_returns_authenticated(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    login_response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    me_response = client.get("/api/auth/me")

    assert login_response.status_code == 200
    assert "pm_auth=user" in login_response.headers["set-cookie"]
    assert me_response.status_code == 200
    assert me_response.json()["status"] == "authenticated"
    assert me_response.json()["username"] == "user"


def test_logout_clears_session_cookie(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client.post("/api/auth/login", json={"username": "user", "password": "password"})

    logout_response = client.post("/api/auth/logout")
    me_response = client.get("/api/auth/me")

    assert logout_response.status_code == 200
    assert "pm_auth=" in logout_response.headers["set-cookie"]
    assert me_response.status_code == 401


def test_ai_chat_requires_authentication(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.post("/api/ai/chat", json={"prompt": "2+2"})

    assert response.status_code == 401


def test_ai_chat_returns_assistant_payload_for_prompt(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    client = make_client(tmp_path)
    client.post("/api/auth/login", json={"username": "user", "password": "password"})

    monkeypatch.setattr("app.main.request_ai_reply", lambda prompt: "4")

    response = client.post("/api/ai/chat", json={"prompt": "2+2"})

    assert response.status_code == 200
    assert response.json()["assistant"]["role"] == "assistant"
    assert response.json()["assistant"]["content"] == "4"
    assert response.json()["model"] == "openai/gpt-oss-120b:free"


def test_ai_chat_returns_bad_request_for_blank_prompt(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client.post("/api/auth/login", json={"username": "user", "password": "password"})

    response = client.post("/api/ai/chat", json={"prompt": "   "})

    assert response.status_code == 400
    assert response.json()["detail"] == "Prompt is required."


def test_ai_chat_returns_timeout_error(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.ai import AITimeoutError

    client = make_client(tmp_path)
    client.post("/api/auth/login", json={"username": "user", "password": "password"})

    def raise_timeout(prompt: str) -> str:
        raise AITimeoutError("AI request timed out.")

    monkeypatch.setattr("app.main.request_ai_reply", raise_timeout)

    response = client.post("/api/ai/chat", json={"prompt": "2+2"})

    assert response.status_code == 504
    assert response.json()["detail"] == "AI request timed out."


def test_ai_chat_returns_provider_error(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.ai import AIProviderError

    client = make_client(tmp_path)
    client.post("/api/auth/login", json={"username": "user", "password": "password"})

    def raise_provider_error(prompt: str) -> str:
        raise AIProviderError("Provider unavailable.")

    monkeypatch.setattr("app.main.request_ai_reply", raise_provider_error)

    response = client.post("/api/ai/chat", json={"prompt": "2+2"})

    assert response.status_code == 502
    assert response.json()["detail"] == "Provider unavailable."


def test_ai_chat_applies_valid_board_update(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    client = make_client(tmp_path)
    client.post("/api/auth/login", json={"username": "user", "password": "password"})

    monkeypatch.setattr(
        "app.main.request_ai_reply",
        lambda prompt: (
            '{"assistantMessage":"Added one task.",'
            '"operations":[{"type":"create_card","columnId":"col-backlog","title":"AI Task","details":"From AI"}]}'
        ),
    )

    response = client.post("/api/ai/chat", json={"prompt": "add a task"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["assistant"]["content"] == "Added one task."
    assert payload["parsed"] is True
    assert payload["boardUpdated"] is True
    assert len(payload["appliedOperations"]) == 1
    assert any(card["title"] == "AI Task" for card in payload["board"]["cards"].values())


def test_ai_chat_unparseable_output_does_not_mutate_board(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    client = make_client(tmp_path)
    client.post("/api/auth/login", json={"username": "user", "password": "password"})

    before = client.get("/api/board").json()["board"]

    monkeypatch.setattr("app.main.request_ai_reply", lambda prompt: "Just a text reply, no JSON.")

    response = client.post("/api/ai/chat", json={"prompt": "do anything"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["parsed"] is False
    assert payload["boardUpdated"] is False
    assert payload["appliedOperations"] == []
    assert payload["operationErrors"] == []
    assert payload["assistant"]["content"] == "Just a text reply, no JSON."

    after = client.get("/api/board").json()["board"]
    assert after == before
