import json
import socket
from urllib import error

import pytest

from app.ai import AIProviderError, AITimeoutError, MissingApiKeyError, request_ai_reply


class FakeHTTPResponse:
    def __init__(self, payload: dict) -> None:
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None


class FakeHTTPError(error.HTTPError):
    def __init__(self, body: dict) -> None:
        super().__init__(
            url="https://openrouter.ai/api/v1/chat/completions",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=None,
        )
        self._body = json.dumps(body).encode("utf-8")

    def read(self) -> bytes:
        return self._body


def test_request_ai_reply_raises_when_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(MissingApiKeyError):
        request_ai_reply("2+2")


def test_request_ai_reply_returns_content(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(req, timeout):  # type: ignore[no-untyped-def]
        return FakeHTTPResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": "4",
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("app.ai.request.urlopen", fake_urlopen)

    content = request_ai_reply("2+2", api_key="test-key")

    assert content == "4"


def test_request_ai_reply_raises_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(req, timeout):  # type: ignore[no-untyped-def]
        raise error.URLError(socket.timeout("timed out"))

    monkeypatch.setattr("app.ai.request.urlopen", fake_urlopen)

    with pytest.raises(AITimeoutError):
        request_ai_reply("2+2", api_key="test-key")


def test_request_ai_reply_raises_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(req, timeout):  # type: ignore[no-untyped-def]
        raise FakeHTTPError({"error": {"message": "Invalid API key"}})

    monkeypatch.setattr("app.ai.request.urlopen", fake_urlopen)

    with pytest.raises(AIProviderError, match="Invalid API key"):
        request_ai_reply("2+2", api_key="bad-key")
