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
    CardNotFoundError,
    ColumnNotFoundError,
    append_chat_message_for_user,
    create_card,
    delete_card,
    get_board_for_user,
    initialize_database,
    list_chat_messages_for_user,
    move_card,
    rename_column,
    update_card,
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


class RenameColumnPayload(BaseModel):
    title: NonEmptyStr


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


class AIChatPayload(BaseModel):
    prompt: str


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
            path="/",
        )
        return {"status": "ok"}

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

    @app.get("/api/board")
    async def get_board(username: str = Depends(require_username)) -> dict:
        try:
            board = get_board_for_user(app.state.db_path, username)
        except BoardNotFoundError:
            raise HTTPException(status_code=404, detail="Board not found.") from None
        return {"board": board}

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

        append_chat_message_for_user(app.state.db_path, username, "user", user_message)

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
