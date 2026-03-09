from pathlib import Path

from app.ai_workflow import apply_ai_operations, parse_ai_output
from app.db import get_board_for_user, initialize_database


def test_parse_ai_output_strict_json_with_operations() -> None:
    raw = (
        '{"assistantMessage":"Done","operations":[{"type":"create_card","columnId":"col-backlog",'
        '"title":"Task A","details":"D"}]}'
    )

    assistant, operations, parsed = parse_ai_output(raw)

    assert parsed is True
    assert assistant == "Done"
    assert operations[0]["type"] == "create_card"
    assert operations[0]["columnId"] == "col-backlog"


def test_parse_ai_output_fallback_json_block_and_coercion() -> None:
    raw = """
Here is the update:
```json
{
  "assistant": {"content": "Moved it."},
  "actions": [{"action": "move", "card_id": "card-1", "column_id": "col-review", "position": 0}]
}
```
"""
    assistant, operations, parsed = parse_ai_output(raw)

    assert parsed is True
    assert assistant == "Moved it."
    assert operations == [
        {"type": "move_card", "cardId": "card-1", "columnId": "col-review", "position": 0}
    ]


def test_parse_ai_output_unparseable_returns_text_without_operations() -> None:
    raw = "I think we should add one task in backlog."

    assistant, operations, parsed = parse_ai_output(raw)

    assert parsed is False
    assert assistant == raw
    assert operations == []


def test_apply_ai_operations_create_edit_move(tmp_path: Path) -> None:
    db_path = tmp_path / "pm.db"
    initialize_database(db_path)

    board_before = get_board_for_user(db_path, "user")
    initial_count = len(board_before["cards"])

    operations = [
        {
            "type": "create_card",
            "columnId": "col-backlog",
            "title": "AI Created",
            "details": "From assistant",
        },
    ]
    board_after_create, applied_create, errors_create = apply_ai_operations(
        db_path,
        "user",
        operations,
    )
    assert errors_create == []
    assert len(applied_create) == 1
    assert len(board_after_create["cards"]) == initial_count + 1

    created_card_id = next(
        card_id
        for card_id, card in board_after_create["cards"].items()
        if card["title"] == "AI Created"
    )

    board_after_edit, applied_edit, errors_edit = apply_ai_operations(
        db_path,
        "user",
        [{"type": "edit_card", "cardId": created_card_id, "title": "AI Edited"}],
    )
    assert errors_edit == []
    assert len(applied_edit) == 1
    assert board_after_edit["cards"][created_card_id]["title"] == "AI Edited"

    board_after_move, applied_move, errors_move = apply_ai_operations(
        db_path,
        "user",
        [{"type": "move_card", "cardId": created_card_id, "columnId": "col-done", "position": 0}],
    )
    assert errors_move == []
    assert len(applied_move) == 1
    done_col = next(col for col in board_after_move["columns"] if col["id"] == "col-done")
    assert done_col["cardIds"][0] == created_card_id


def test_apply_ai_operations_invalid_payload_does_not_mutate_board(tmp_path: Path) -> None:
    db_path = tmp_path / "pm.db"
    initialize_database(db_path)

    board_before = get_board_for_user(db_path, "user")

    board_after, applied, errors = apply_ai_operations(
        db_path,
        "user",
        [{"type": "move_card", "cardId": "card-1"}],
    )

    assert applied == []
    assert len(errors) == 1
    assert board_after == board_before
