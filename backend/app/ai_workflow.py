import json
import re
from pathlib import Path
from typing import Any

from app.db import (
    CardNotFoundError,
    ColumnNotFoundError,
    _build_board_payload,
    _connect,
    _do_create_card,
    _do_move_card,
    _do_update_card,
    _get_board_id,
    _validate_board_ownership,
)

OPERATION_TYPES = {"create_card", "edit_card", "move_card"}


def build_ai_prompt(board: dict, chat_history: list[dict[str, str]], user_message: str) -> str:
    payload = {
        "instructions": (
            "You are a project-management assistant. "
            "Return JSON only. Do not use markdown. "
            "Use this schema: "
            '{"assistantMessage":"string","operations":[{"type":"create_card|edit_card|move_card",'
            '"columnId":"...", "cardId":"...", "title":"...", "details":"...", "position":0}]}. '
            "Only include fields needed by each operation."
        ),
        "board": board,
        "chatHistory": chat_history,
        "userMessage": user_message,
    }
    return json.dumps(payload, ensure_ascii=True)


def _normalize_operation(raw_op: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(raw_op, dict):
        return None

    op_type = raw_op.get("type") or raw_op.get("action") or raw_op.get("op")
    if not isinstance(op_type, str):
        return None

    normalized_type = op_type.strip().lower()
    type_aliases = {
        "create": "create_card",
        "createcard": "create_card",
        "add_card": "create_card",
        "edit": "edit_card",
        "update": "edit_card",
        "update_card": "edit_card",
        "editcard": "edit_card",
        "move": "move_card",
        "movecard": "move_card",
    }
    normalized_type = type_aliases.get(normalized_type, normalized_type)
    if normalized_type not in OPERATION_TYPES:
        return None

    normalized: dict[str, Any] = {"type": normalized_type}

    if "cardId" in raw_op or "card_id" in raw_op:
        normalized["cardId"] = raw_op.get("cardId", raw_op.get("card_id"))
    if "columnId" in raw_op or "column_id" in raw_op:
        normalized["columnId"] = raw_op.get("columnId", raw_op.get("column_id"))
    if "title" in raw_op:
        normalized["title"] = raw_op.get("title")
    if "details" in raw_op or "description" in raw_op:
        normalized["details"] = raw_op.get("details", raw_op.get("description"))
    if "position" in raw_op:
        normalized["position"] = raw_op.get("position")

    return normalized


def _coerce_response(parsed: dict[str, Any], fallback_text: str) -> tuple[str, list[dict[str, Any]]]:
    assistant_message = parsed.get("assistantMessage")
    if not isinstance(assistant_message, str):
        assistant_message = parsed.get("assistant_message")
    if not isinstance(assistant_message, str):
        assistant = parsed.get("assistant")
        if isinstance(assistant, dict) and isinstance(assistant.get("content"), str):
            assistant_message = assistant["content"]

    raw_operations = parsed.get("operations")
    if not isinstance(raw_operations, list):
        raw_operations = parsed.get("actions")
    if not isinstance(raw_operations, list):
        raw_operations = parsed.get("boardUpdates")
    if not isinstance(raw_operations, list):
        raw_operations = []

    operations: list[dict[str, Any]] = []
    for raw_op in raw_operations:
        if not isinstance(raw_op, dict):
            continue
        normalized = _normalize_operation(raw_op)
        if normalized is not None:
            operations.append(normalized)

    message = (assistant_message or fallback_text).strip()
    return message, operations


def _extract_json_candidate(raw_output: str) -> list[str]:
    candidates = [raw_output.strip()]

    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_output, re.IGNORECASE)
    if fence_match:
        candidates.append(fence_match.group(1).strip())

    first_brace = raw_output.find("{")
    last_brace = raw_output.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidates.append(raw_output[first_brace : last_brace + 1].strip())

    seen = set()
    unique: list[str] = []
    for value in candidates:
        if value and value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def parse_ai_output(raw_output: str) -> tuple[str, list[dict[str, Any]], bool]:
    fallback_text = raw_output.strip() or "I could not generate a response."

    for candidate in _extract_json_candidate(raw_output):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue

        if not isinstance(parsed, dict):
            continue
        message, operations = _coerce_response(parsed, fallback_text)
        return message or fallback_text, operations, True

    return fallback_text, [], False


def _validate_create_payload(operation: dict[str, Any]) -> tuple[str, str, str] | None:
    column_id = operation.get("columnId")
    title = operation.get("title")
    details = operation.get("details", "")
    if not isinstance(column_id, str) or not column_id.strip():
        return None
    if not isinstance(title, str) or not title.strip():
        return None
    if not isinstance(details, str):
        details = ""
    return column_id.strip(), title.strip(), details.strip()


def _validate_edit_payload(operation: dict[str, Any]) -> tuple[str, str | None, str | None] | None:
    card_id = operation.get("cardId")
    title = operation.get("title")
    details = operation.get("details")
    if not isinstance(card_id, str) or not card_id.strip():
        return None
    if title is not None and not isinstance(title, str):
        return None
    if details is not None and not isinstance(details, str):
        return None
    if title is None and details is None:
        return None
    return card_id.strip(), title.strip() if isinstance(title, str) else None, details.strip() if isinstance(details, str) else None


def _validate_move_payload(operation: dict[str, Any]) -> tuple[str, str, int | None] | None:
    card_id = operation.get("cardId")
    column_id = operation.get("columnId")
    position = operation.get("position")
    if not isinstance(card_id, str) or not card_id.strip():
        return None
    if not isinstance(column_id, str) or not column_id.strip():
        return None
    if position is not None and not isinstance(position, int):
        return None
    if position is not None and position < 0:
        return None
    return card_id.strip(), column_id.strip(), position


def apply_ai_operations(
    db_path: Path,
    username: str,
    operations: list[dict[str, Any]],
) -> tuple[dict, list[dict[str, Any]], list[str]]:
    """Apply a list of AI-generated board operations in a single DB transaction."""
    applied: list[dict[str, Any]] = []
    errors: list[str] = []

    with _connect(db_path) as connection:
        board_id = _get_board_id(connection, username)

        for index, operation in enumerate(operations):
            op_type = operation.get("type")
            try:
                if op_type == "create_card":
                    create_data = _validate_create_payload(operation)
                    if create_data is None:
                        errors.append(f"Operation {index} invalid create_card payload.")
                        continue
                    column_id, title, details = create_data
                    _do_create_card(connection, board_id, column_id, title, details)
                    applied.append({"index": index, "type": op_type})
                    continue

                if op_type == "edit_card":
                    edit_data = _validate_edit_payload(operation)
                    if edit_data is None:
                        errors.append(f"Operation {index} invalid edit_card payload.")
                        continue
                    card_id, title, details = edit_data
                    _do_update_card(connection, board_id, card_id, title, details)
                    applied.append({"index": index, "type": op_type, "cardId": card_id})
                    continue

                if op_type == "move_card":
                    move_data = _validate_move_payload(operation)
                    if move_data is None:
                        errors.append(f"Operation {index} invalid move_card payload.")
                        continue
                    card_id, column_id, position = move_data
                    _do_move_card(connection, board_id, card_id, column_id, position)
                    applied.append(
                        {
                            "index": index,
                            "type": op_type,
                            "cardId": card_id,
                            "columnId": column_id,
                        }
                    )
                    continue

                errors.append(f"Operation {index} has unsupported type.")
            except (ColumnNotFoundError, CardNotFoundError) as exc:
                errors.append(f"Operation {index} failed: {exc.__class__.__name__}.")

        board = _build_board_payload(connection, board_id)

    return board, applied, errors


def apply_ai_operations_on_board(
    db_path: Path,
    username: str,
    board_id: str,
    operations: list[dict[str, Any]],
) -> tuple[dict, list[dict[str, Any]], list[str]]:
    """Apply AI-generated operations scoped to a specific board."""
    applied: list[dict[str, Any]] = []
    errors: list[str] = []

    with _connect(db_path) as connection:
        _validate_board_ownership(connection, username, board_id)

        for index, operation in enumerate(operations):
            op_type = operation.get("type")
            try:
                if op_type == "create_card":
                    create_data = _validate_create_payload(operation)
                    if create_data is None:
                        errors.append(f"Operation {index} invalid create_card payload.")
                        continue
                    column_id, title, details = create_data
                    _do_create_card(connection, board_id, column_id, title, details)
                    applied.append({"index": index, "type": op_type})
                    continue

                if op_type == "edit_card":
                    edit_data = _validate_edit_payload(operation)
                    if edit_data is None:
                        errors.append(f"Operation {index} invalid edit_card payload.")
                        continue
                    card_id, title, details = edit_data
                    _do_update_card(connection, board_id, card_id, title, details)
                    applied.append({"index": index, "type": op_type, "cardId": card_id})
                    continue

                if op_type == "move_card":
                    move_data = _validate_move_payload(operation)
                    if move_data is None:
                        errors.append(f"Operation {index} invalid move_card payload.")
                        continue
                    card_id, column_id, position = move_data
                    _do_move_card(connection, board_id, card_id, column_id, position)
                    applied.append(
                        {
                            "index": index,
                            "type": op_type,
                            "cardId": card_id,
                            "columnId": column_id,
                        }
                    )
                    continue

                errors.append(f"Operation {index} has unsupported type.")
            except (ColumnNotFoundError, CardNotFoundError) as exc:
                errors.append(f"Operation {index} failed: {exc.__class__.__name__}.")

        board = _build_board_payload(connection, board_id)

    return board, applied, errors
