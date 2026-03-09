import json
import os
import socket
from urllib import error, request

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openai/gpt-oss-120b:free"


class MissingApiKeyError(Exception):
    pass


class AITimeoutError(Exception):
    pass


class AIProviderError(Exception):
    pass


def _extract_content(payload: dict) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AIProviderError("AI provider returned an invalid response payload.")

    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise AIProviderError("AI provider returned an invalid response payload.")

    content = message.get("content")
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts = []
        for chunk in content:
            if not isinstance(chunk, dict):
                continue
            if chunk.get("type") == "text" and isinstance(chunk.get("text"), str):
                text_parts.append(chunk["text"])
        if text_parts:
            return "\n".join(text_parts).strip()

    raise AIProviderError("AI provider returned an invalid response payload.")


def request_ai_reply(prompt: str, api_key: str | None = None, timeout_seconds: float = 20.0) -> str:
    key = api_key or os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise MissingApiKeyError("OPENROUTER_API_KEY is not configured.")

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        OPENROUTER_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        raw_error = ""
        try:
            raw_error = exc.read().decode("utf-8")
        except Exception:
            raw_error = ""

        detail = "AI provider request failed."
        if raw_error:
            try:
                parsed = json.loads(raw_error)
                message = parsed.get("error", {}).get("message")
                if isinstance(message, str) and message.strip():
                    detail = message.strip()
            except json.JSONDecodeError:
                pass
        raise AIProviderError(detail) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise AITimeoutError("AI request timed out.") from exc
    except error.URLError as exc:
        if isinstance(exc.reason, TimeoutError | socket.timeout):
            raise AITimeoutError("AI request timed out.") from exc
        raise AIProviderError("AI provider request failed.") from exc

    try:
        payload_data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AIProviderError("AI provider returned an invalid response payload.") from exc

    content = _extract_content(payload_data)
    if not content:
        raise AIProviderError("AI provider returned an empty response.")
    return content
