import os
import secrets
from pathlib import Path
from typing import Annotated

from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StringConstraints

from app.ai import (
    AIProviderError,
    AITimeoutError,
    MissingApiKeyError,
    request_ai_reply,
)
from app.ai_workflow import apply_ai_operations, build_ai_prompt, parse_ai_output
from app.db import (
    BoardNotFoundError,
    BoardPermissionError,
    CardNotFoundError,
    ColumnNotFoundError,
    UserAlreadyExistsError,
    add_column,
    append_chat_message_for_board,
    append_chat_message_for_user,
    change_password,
    create_board,
    create_card,
    create_card_on_board,
    delete_board,
    delete_card,
    delete_card_on_board,
    delete_column,
    get_board_by_id,
    get_board_for_user,
    initialize_database,
    list_boards_for_user,
    list_chat_messages_for_board,
    list_chat_messages_for_user,
    move_card,
    move_card_on_board,
    register_user,
    rename_board,
    rename_column,
    rename_column_on_board,
    update_card,
    update_card_on_board,
    user_exists,
    verify_credentials,
)

DEFAULT_STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "pm.db"
AUTH_COOKIE_NAME = "pm_auth"

# Shared type for non-empty stripped strings used in payloads.
NonEmptyStr = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]


class LoginPayload(BaseModel):
    username: str
    password: str


class RegisterPayload(BaseModel):
    username: NonEmptyStr
    password: Annotated[str, StringConstraints(min_length=6)]


class ChangePasswordPayload(BaseModel):
    current_password: str
    new_password: Annotated[str, StringConstraints(min_length=6)]


class RenameColumnPayload(BaseModel):
    title: NonEmptyStr


class AddColumnPayload(BaseModel):
    title: NonEmptyStr


class CreateBoardPayload(BaseModel):
    name: NonEmptyStr


class RenameBoardPayload(BaseModel):
    name: NonEmptyStr


class CreateCardPayload(BaseModel):
    columnId: str
    title: NonEmptyStr
    details: str = ""


class UpdateCardPayload(BaseModel):
    title: str | None = None
    details: str | None = None


class MoveCardPayload(BaseModel):
    columnId: str
    position: int | None = None


_PROMPT_MAX_LENGTH = 2000


class AIChatPayload(BaseModel):
    prompt: Annotated[str, StringConstraints(max_length=_PROMPT_MAX_LENGTH)]


def resolve_frontend_dir() -> Path:
    env_path = Path(os.environ.get("FRONTEND_DIST", str(DEFAULT_STATIC_DIR)))
    return env_path if env_path.exists() else DEFAULT_STATIC_DIR


def resolve_db_path() -> Path:
    return Path(os.environ.get("DB_PATH", str(DEFAULT_DB_PATH)))


def create_app(frontend_dir: Path | None = None, db_path: Path | None = None) -> FastAPI:
    app = FastAPI(title="Project Management MVP API")
    app.state.db_path = db_path or resolve_db_path()
    app.state.sessions: dict[str, str] = {}  # token -> username
    initialize_database(app.state.db_path)

    def require_username(
        request: Request,
        pm_auth: str | None = Cookie(default=None),
    ) -> str:
        if not pm_auth:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated.",
            )
        username = request.app.state.sessions.get(pm_auth)
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated.",
            )
        return username

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "pm-backend"}

    # ===== Auth =====

    @app.post("/api/auth/login")
    async def login(payload: LoginPayload, response: Response, request: Request) -> dict[str, str]:
        if not verify_credentials(app.state.db_path, payload.username, payload.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password.",
            )

        token = secrets.token_hex(32)
        request.app.state.sessions[token] = payload.username
        response.set_cookie(
            key=AUTH_COOKIE_NAME,
            value=token,
            httponly=True,
            samesite="lax",
            secure=os.environ.get("SECURE_COOKIES", "0") == "1",
            path="/",
        )
        return {"status": "ok"}

    @app.post("/api/auth/register")
    async def register(payload: RegisterPayload, response: Response, request: Request) -> dict[str, str]:
        try:
            register_user(app.state.db_path, payload.username, payload.password)
        except UserAlreadyExistsError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken.",
            ) from None

        token = secrets.token_hex(32)
        request.app.state.sessions[token] = payload.username
        response.set_cookie(
            key=AUTH_COOKIE_NAME,
            value=token,
            httponly=True,
            samesite="lax",
            secure=os.environ.get("SECURE_COOKIES", "0") == "1",
            path="/",
        )
        return {"status": "ok", "username": payload.username}

    @app.post("/api/auth/logout")
    async def logout(
        response: Response,
        request: Request,
        pm_auth: str | None = Cookie(default=None),
    ) -> dict[str, str]:
        if pm_auth:
            request.app.state.sessions.pop(pm_auth, None)
        response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
        return {"status": "ok"}

    @app.get("/api/auth/me")
    async def me(username: str = Depends(require_username)) -> dict[str, str]:
        if not user_exists(app.state.db_path, username):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated.",
            )
        return {"status": "authenticated", "username": username}

    @app.patch("/api/auth/password")
    async def update_password(
        payload: ChangePasswordPayload,
        username: str = Depends(require_username),
    ) -> dict[str, str]:
        success = change_password(
            app.state.db_path,
            username,
            payload.current_password,
            payload.new_password,
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect.",
            )
        return {"status": "ok"}

    # ===== Legacy single-board endpoint (backward compat) =====

    @app.get("/api/board")
    async def get_board(username: str = Depends(require_username)) -> dict:
        try:
            board = get_board_for_user(app.state.db_path, username)
        except BoardNotFoundError:
            raise HTTPException(status_code=404, detail="Board not found.") from None
        return {"board": board}

    # ===== Board management =====

    @app.get("/api/boards")
    async def list_boards(username: str = Depends(require_username)) -> dict:
        boards = list_boards_for_user(app.state.db_path, username)
        return {"boards": boards}

    @app.post("/api/boards")
    async def post_board(
        payload: CreateBoardPayload,
        username: str = Depends(require_username),
    ) -> dict:
        board = create_board(app.state.db_path, username, payload.name)
        return {"board": board}

    @app.get("/api/boards/{board_id}")
    async def get_board_by_id_route(
        board_id: str,
        username: str = Depends(require_username),
    ) -> dict:
        try:
            board = get_board_by_id(app.state.db_path, username, board_id)
        except BoardNotFoundError:
            raise HTTPException(status_code=404, detail="Board not found.") from None
        return {"board": board}

    @app.patch("/api/boards/{board_id}")
    async def patch_board(
        board_id: str,
        payload: RenameBoardPayload,
        username: str = Depends(require_username),
    ) -> dict:
        try:
            board = rename_board(app.state.db_path, username, board_id, payload.name)
        except BoardNotFoundError:
            raise HTTPException(status_code=404, detail="Board not found.") from None
        return {"board": board}

    @app.delete("/api/boards/{board_id}")
    async def remove_board(
        board_id: str,
        username: str = Depends(require_username),
    ) -> dict[str, str]:
        try:
            delete_board(app.state.db_path, username, board_id)
        except BoardNotFoundError:
            raise HTTPException(status_code=404, detail="Board not found.") from None
        except BoardPermissionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"status": "ok"}

    # ===== Board-scoped column management =====

    @app.post("/api/boards/{board_id}/columns")
    async def add_column_to_board(
        board_id: str,
        payload: AddColumnPayload,
        username: str = Depends(require_username),
    ) -> dict:
        try:
            board = add_column(app.state.db_path, username, board_id, payload.title)
        except BoardNotFoundError:
            raise HTTPException(status_code=404, detail="Board not found.") from None
        return {"board": board}

    @app.patch("/api/boards/{board_id}/columns/{column_id}")
    async def patch_column_on_board(
        board_id: str,
        column_id: str,
        payload: RenameColumnPayload,
        username: str = Depends(require_username),
    ) -> dict:
        try:
            board = rename_column_on_board(
                app.state.db_path, username, board_id, column_id, payload.title
            )
        except BoardNotFoundError:
            raise HTTPException(status_code=404, detail="Board not found.") from None
        except ColumnNotFoundError:
            raise HTTPException(status_code=404, detail="Column not found.") from None
        return {"board": board}

    @app.delete("/api/boards/{board_id}/columns/{column_id}")
    async def remove_column_from_board(
        board_id: str,
        column_id: str,
        username: str = Depends(require_username),
    ) -> dict:
        try:
            board = delete_column(app.state.db_path, username, board_id, column_id)
        except BoardNotFoundError:
            raise HTTPException(status_code=404, detail="Board not found.") from None
        except ColumnNotFoundError:
            raise HTTPException(status_code=404, detail="Column not found.") from None
        return {"board": board}

    # ===== Board-scoped card management =====

    @app.post("/api/boards/{board_id}/cards")
    async def post_card_on_board(
        board_id: str,
        payload: CreateCardPayload,
        username: str = Depends(require_username),
    ) -> dict:
        try:
            board = create_card_on_board(
                app.state.db_path,
                username,
                board_id,
                payload.columnId,
                payload.title,
                payload.details.strip(),
            )
        except BoardNotFoundError:
            raise HTTPException(status_code=404, detail="Board not found.") from None
        except ColumnNotFoundError:
            raise HTTPException(status_code=404, detail="Column not found.") from None
        return {"board": board}

    @app.patch("/api/boards/{board_id}/cards/{card_id}")
    async def patch_card_on_board(
        board_id: str,
        card_id: str,
        payload: UpdateCardPayload,
        username: str = Depends(require_username),
    ) -> dict:
        try:
            board = update_card_on_board(
                app.state.db_path,
                username,
                board_id,
                card_id,
                payload.title.strip() if payload.title is not None else None,
                payload.details.strip() if payload.details is not None else None,
            )
        except BoardNotFoundError:
            raise HTTPException(status_code=404, detail="Board not found.") from None
        except CardNotFoundError:
            raise HTTPException(status_code=404, detail="Card not found.") from None
        return {"board": board}

    @app.delete("/api/boards/{board_id}/cards/{card_id}")
    async def remove_card_on_board(
        board_id: str,
        card_id: str,
        username: str = Depends(require_username),
    ) -> dict:
        try:
            board = delete_card_on_board(app.state.db_path, username, board_id, card_id)
        except BoardNotFoundError:
            raise HTTPException(status_code=404, detail="Board not found.") from None
        except CardNotFoundError:
            raise HTTPException(status_code=404, detail="Card not found.") from None
        return {"board": board}

    @app.post("/api/boards/{board_id}/cards/{card_id}/move")
    async def post_move_card_on_board(
        board_id: str,
        card_id: str,
        payload: MoveCardPayload,
        username: str = Depends(require_username),
    ) -> dict:
        try:
            board = move_card_on_board(
                app.state.db_path,
                username,
                board_id,
                card_id,
                payload.columnId,
                payload.position,
            )
        except BoardNotFoundError:
            raise HTTPException(status_code=404, detail="Board not found.") from None
        except CardNotFoundError:
            raise HTTPException(status_code=404, detail="Card not found.") from None
        except ColumnNotFoundError:
            raise HTTPException(status_code=404, detail="Column not found.") from None
        return {"board": board}

    # ===== Board-scoped AI chat =====

    @app.post("/api/boards/{board_id}/chat")
    async def post_board_ai_chat(
        board_id: str,
        payload: AIChatPayload,
        username: str = Depends(require_username),
    ) -> dict:
        user_message = payload.prompt.strip()
        if not user_message:
            raise HTTPException(status_code=400, detail="Prompt is required.")

        try:
            board_snapshot = get_board_by_id(app.state.db_path, username, board_id)
        except BoardNotFoundError:
            raise HTTPException(status_code=404, detail="Board not found.") from None

        chat_history = list_chat_messages_for_board(app.state.db_path, username, board_id)
        prompt = build_ai_prompt(board_snapshot, chat_history, user_message)

        try:
            raw_output = request_ai_reply(prompt)
        except MissingApiKeyError:
            raise HTTPException(
                status_code=500,
                detail="OPENROUTER_API_KEY is not configured.",
            ) from None
        except AITimeoutError:
            raise HTTPException(status_code=504, detail="AI request timed out.") from None
        except AIProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from None

        assistant_text, operations, parsed = parse_ai_output(raw_output)

        from app.ai_workflow import apply_ai_operations_on_board
        board, applied_operations, operation_errors = apply_ai_operations_on_board(
            app.state.db_path,
            username,
            board_id,
            operations,
        )
        append_chat_message_for_board(app.state.db_path, username, board_id, "user", user_message)
        append_chat_message_for_board(
            app.state.db_path,
            username,
            board_id,
            "assistant",
            assistant_text,
            metadata={
                "parsed": parsed,
                "requestedOperationCount": len(operations),
                "appliedOperationCount": len(applied_operations),
                "operationErrors": operation_errors,
            },
        )

        return {
            "assistant": {"role": "assistant", "content": assistant_text},
            "parsed": parsed,
            "boardUpdated": len(applied_operations) > 0,
            "appliedOperations": applied_operations,
            "operationErrors": operation_errors,
            "board": board,
        }

    # ===== Legacy card/column routes (backward compat, operate on default board) =====

    @app.patch("/api/columns/{column_id}")
    async def patch_column(
        column_id: str,
        payload: RenameColumnPayload,
        username: str = Depends(require_username),
    ) -> dict:
        try:
            board = rename_column(app.state.db_path, username, column_id, payload.title)
        except ColumnNotFoundError:
            raise HTTPException(status_code=404, detail="Column not found.") from None
        return {"board": board}

    @app.post("/api/cards")
    async def post_card(
        payload: CreateCardPayload,
        username: str = Depends(require_username),
    ) -> dict:
        try:
            board = create_card(
                app.state.db_path,
                username,
                payload.columnId,
                payload.title,
                payload.details.strip(),
            )
        except ColumnNotFoundError:
            raise HTTPException(status_code=404, detail="Column not found.") from None
        return {"board": board}

    @app.patch("/api/cards/{card_id}")
    async def patch_card(
        card_id: str,
        payload: UpdateCardPayload,
        username: str = Depends(require_username),
    ) -> dict:
        try:
            board = update_card(
                app.state.db_path,
                username,
                card_id,
                payload.title.strip() if payload.title is not None else None,
                payload.details.strip() if payload.details is not None else None,
            )
        except CardNotFoundError:
            raise HTTPException(status_code=404, detail="Card not found.") from None
        return {"board": board}

    @app.delete("/api/cards/{card_id}")
    async def remove_card(
        card_id: str,
        username: str = Depends(require_username),
    ) -> dict:
        try:
            board = delete_card(app.state.db_path, username, card_id)
        except CardNotFoundError:
            raise HTTPException(status_code=404, detail="Card not found.") from None
        return {"board": board}

    @app.post("/api/cards/{card_id}/move")
    async def post_move_card(
        card_id: str,
        payload: MoveCardPayload,
        username: str = Depends(require_username),
    ) -> dict:
        try:
            board = move_card(
                app.state.db_path,
                username,
                card_id,
                payload.columnId,
                payload.position,
            )
        except CardNotFoundError:
            raise HTTPException(status_code=404, detail="Card not found.") from None
        except ColumnNotFoundError:
            raise HTTPException(status_code=404, detail="Column not found.") from None
        return {"board": board}

    @app.post("/api/ai/chat")
    async def post_ai_chat(
        payload: AIChatPayload,
        username: str = Depends(require_username),
    ) -> dict:
        user_message = payload.prompt.strip()
        if not user_message:
            raise HTTPException(status_code=400, detail="Prompt is required.")

        board_snapshot = get_board_for_user(app.state.db_path, username)
        chat_history = list_chat_messages_for_user(app.state.db_path, username)
        prompt = build_ai_prompt(board_snapshot, chat_history, user_message)

        try:
            raw_output = request_ai_reply(prompt)
        except MissingApiKeyError:
            raise HTTPException(
                status_code=500,
                detail="OPENROUTER_API_KEY is not configured.",
            ) from None
        except AITimeoutError:
            raise HTTPException(status_code=504, detail="AI request timed out.") from None
        except AIProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from None

        assistant_text, operations, parsed = parse_ai_output(raw_output)
        board, applied_operations, operation_errors = apply_ai_operations(
            app.state.db_path,
            username,
            operations,
        )
        append_chat_message_for_user(app.state.db_path, username, "user", user_message)
        append_chat_message_for_user(
            app.state.db_path,
            username,
            "assistant",
            assistant_text,
            metadata={
                "parsed": parsed,
                "requestedOperationCount": len(operations),
                "appliedOperationCount": len(applied_operations),
                "operationErrors": operation_errors,
            },
        )

        return {
            "assistant": {"role": "assistant", "content": assistant_text},
            "parsed": parsed,
            "boardUpdated": len(applied_operations) > 0,
            "appliedOperations": applied_operations,
            "operationErrors": operation_errors,
            "board": board,
        }

    app.mount(
        "/",
        StaticFiles(directory=frontend_dir or resolve_frontend_dir(), html=True),
        name="frontend",
    )

    return app


app = create_app()
