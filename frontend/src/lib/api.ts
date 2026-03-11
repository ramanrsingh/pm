import type { BoardData } from "@/lib/kanban";

type BoardApiCard = {
  id: string;
  title: string;
  details: string;
  metadata?: unknown;
};

type BoardApiPayload = {
  id: string;
  name: string;
  columns: BoardData["columns"];
  cards: Record<string, BoardApiCard>;
};

type BoardApiResponse = {
  board: BoardApiPayload;
};

export type BoardSummary = {
  id: string;
  name: string;
  createdAt: string;
};

export type AIChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type AIChatApiResponse = {
  assistant: AIChatMessage;
  parsed: boolean;
  boardUpdated: boolean;
  appliedOperations: Array<{
    index: number;
    type: string;
    cardId?: string;
    columnId?: string;
  }>;
  operationErrors: string[];
  board: BoardApiPayload;
};

const toBoardData = (payload: BoardApiResponse): BoardData => {
  return {
    id: payload.board.id,
    name: payload.board.name,
    columns: payload.board.columns,
    cards: Object.fromEntries(
      Object.entries(payload.board.cards).map(([id, card]) => [
        id,
        {
          id: card.id,
          title: card.title,
          details: card.details,
        },
      ])
    ),
  };
};

const requestJson = async <T>(url: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(url, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        detail = payload.detail;
      }
    } catch {
      // Keep fallback detail.
    }
    throw new Error(detail);
  }

  return (await response.json()) as T;
};

// ===== Auth =====

export const register = async (username: string, password: string): Promise<void> => {
  await requestJson("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
};

export const changePassword = async (
  currentPassword: string,
  newPassword: string
): Promise<void> => {
  await requestJson("/api/auth/password", {
    method: "PATCH",
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
};

// ===== Board list =====

export const fetchBoards = async (): Promise<BoardSummary[]> => {
  const payload = await requestJson<{ boards: BoardSummary[] }>("/api/boards", { method: "GET" });
  return payload.boards;
};

export const createBoard = async (name: string): Promise<BoardData> => {
  const payload = await requestJson<BoardApiResponse>("/api/boards", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
  return toBoardData(payload);
};

export const renameBoard = async (boardId: string, name: string): Promise<BoardData> => {
  const payload = await requestJson<BoardApiResponse>(`/api/boards/${boardId}`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
  return toBoardData(payload);
};

export const deleteBoard = async (boardId: string): Promise<void> => {
  await requestJson(`/api/boards/${boardId}`, { method: "DELETE" });
};

// ===== Board fetch =====

export const fetchBoard = async (): Promise<BoardData> => {
  const payload = await requestJson<BoardApiResponse>("/api/board", {
    method: "GET",
  });
  return toBoardData(payload);
};

export const fetchBoardById = async (boardId: string): Promise<BoardData> => {
  const payload = await requestJson<BoardApiResponse>(`/api/boards/${boardId}`, {
    method: "GET",
  });
  return toBoardData(payload);
};

// ===== Column management =====

export const addColumn = async (boardId: string, title: string): Promise<BoardData> => {
  const payload = await requestJson<BoardApiResponse>(
    `/api/boards/${boardId}/columns`,
    {
      method: "POST",
      body: JSON.stringify({ title }),
    }
  );
  return toBoardData(payload);
};

export const renameColumn = async (
  columnId: string,
  title: string,
  boardId?: string
): Promise<BoardData> => {
  const url = boardId
    ? `/api/boards/${boardId}/columns/${columnId}`
    : `/api/columns/${columnId}`;
  const payload = await requestJson<BoardApiResponse>(url, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
  return toBoardData(payload);
};

export const deleteColumn = async (boardId: string, columnId: string): Promise<BoardData> => {
  const payload = await requestJson<BoardApiResponse>(
    `/api/boards/${boardId}/columns/${columnId}`,
    { method: "DELETE" }
  );
  return toBoardData(payload);
};

// ===== Card management =====

export const createCard = async (
  columnId: string,
  title: string,
  details: string,
  boardId?: string
): Promise<BoardData> => {
  const url = boardId ? `/api/boards/${boardId}/cards` : "/api/cards";
  const payload = await requestJson<BoardApiResponse>(url, {
    method: "POST",
    body: JSON.stringify({ columnId, title, details }),
  });
  return toBoardData(payload);
};

export const deleteCard = async (cardId: string, boardId?: string): Promise<BoardData> => {
  const url = boardId ? `/api/boards/${boardId}/cards/${cardId}` : `/api/cards/${cardId}`;
  const payload = await requestJson<BoardApiResponse>(url, {
    method: "DELETE",
  });
  return toBoardData(payload);
};

export const moveCard = async (
  cardId: string,
  columnId: string,
  position: number | null,
  boardId?: string
): Promise<BoardData> => {
  const url = boardId
    ? `/api/boards/${boardId}/cards/${cardId}/move`
    : `/api/cards/${cardId}/move`;
  const payload = await requestJson<BoardApiResponse>(url, {
    method: "POST",
    body: JSON.stringify({ columnId, position }),
  });
  return toBoardData(payload);
};

export const chatWithAssistant = async (
  prompt: string,
  boardId?: string
): Promise<{
  assistant: AIChatMessage;
  board: BoardData;
  boardUpdated: boolean;
  operationErrors: string[];
}> => {
  const url = boardId ? `/api/boards/${boardId}/chat` : "/api/ai/chat";
  const payload = await requestJson<AIChatApiResponse>(url, {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });

  return {
    assistant: payload.assistant,
    board: toBoardData({ board: payload.board }),
    boardUpdated: payload.boardUpdated,
    operationErrors: payload.operationErrors,
  };
};
