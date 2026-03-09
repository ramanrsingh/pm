import type { BoardData } from "@/lib/kanban";

type BoardApiCard = {
  id: string;
  title: string;
  details: string;
  metadata?: unknown;
};

type BoardApiResponse = {
  board: {
    columns: BoardData["columns"];
    cards: Record<string, BoardApiCard>;
  };
};

export type AIChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type AIChatApiResponse = {
  assistant: AIChatMessage;
  model: string;
  parsed: boolean;
  boardUpdated: boolean;
  appliedOperations: Array<{
    index: number;
    type: string;
    cardId?: string;
    columnId?: string;
  }>;
  operationErrors: string[];
  board: BoardApiResponse["board"];
};

const toBoardData = (payload: BoardApiResponse): BoardData => {
  return {
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

export const fetchBoard = async (): Promise<BoardData> => {
  const payload = await requestJson<BoardApiResponse>("/api/board", {
    method: "GET",
  });
  return toBoardData(payload);
};

export const renameColumn = async (
  columnId: string,
  title: string
): Promise<BoardData> => {
  const payload = await requestJson<BoardApiResponse>(`/api/columns/${columnId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
  return toBoardData(payload);
};

export const createCard = async (
  columnId: string,
  title: string,
  details: string
): Promise<BoardData> => {
  const payload = await requestJson<BoardApiResponse>("/api/cards", {
    method: "POST",
    body: JSON.stringify({ columnId, title, details }),
  });
  return toBoardData(payload);
};

export const deleteCard = async (cardId: string): Promise<BoardData> => {
  const payload = await requestJson<BoardApiResponse>(`/api/cards/${cardId}`, {
    method: "DELETE",
  });
  return toBoardData(payload);
};

export const moveCard = async (
  cardId: string,
  columnId: string,
  position: number | null
): Promise<BoardData> => {
  const payload = await requestJson<BoardApiResponse>(`/api/cards/${cardId}/move`, {
    method: "POST",
    body: JSON.stringify({ columnId, position }),
  });
  return toBoardData(payload);
};

export const chatWithAssistant = async (
  prompt: string
): Promise<{
  assistant: AIChatMessage;
  board: BoardData;
  boardUpdated: boolean;
  operationErrors: string[];
}> => {
  const payload = await requestJson<AIChatApiResponse>("/api/ai/chat", {
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
