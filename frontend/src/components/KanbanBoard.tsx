"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  closestCorners,
  type DragEndEvent,
  type DragStartEvent,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";
import { KanbanColumn } from "@/components/KanbanColumn";
import {
  chatWithAssistant,
  createCard,
  deleteCard,
  fetchBoard,
  moveCard,
  renameColumn,
  type AIChatMessage,
} from "@/lib/api";
import type { BoardData } from "@/lib/kanban";

type KanbanBoardProps = {
  onLogout?: () => void;
};

const getColumnIdForCard = (board: BoardData, cardId: string): string | undefined => {
  return board.columns.find((column) => column.cardIds.includes(cardId))?.id;
};

const getMoveTarget = (
  board: BoardData,
  activeId: string,
  overId: string
): { columnId: string; position: number | null } | null => {
  const overColumn = board.columns.find((column) => column.id === overId);
  if (overColumn) {
    return { columnId: overColumn.id, position: overColumn.cardIds.length };
  }

  const destinationColumnId = getColumnIdForCard(board, overId);
  if (!destinationColumnId) {
    return null;
  }

  const destinationColumn = board.columns.find((column) => column.id === destinationColumnId);
  if (!destinationColumn) {
    return null;
  }

  const position = destinationColumn.cardIds.indexOf(overId);
  if (position < 0) {
    return { columnId: destinationColumnId, position: null };
  }

  return { columnId: destinationColumnId, position };
};

export const KanbanBoard = ({ onLogout }: KanbanBoardProps) => {
  const [board, setBoard] = useState<BoardData | null>(null);
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<AIChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatError, setChatError] = useState<string | null>(null);
  const [isChatSubmitting, setIsChatSubmitting] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    })
  );

  const loadBoard = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const nextBoard = await fetchBoard();
      setBoard(nextBoard);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to load board.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadBoard();
  }, []);

  const applyMutation = async (mutation: () => Promise<BoardData>) => {
    try {
      const nextBoard = await mutation();
      setBoard(nextBoard);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to update board.";
      setError(message);
    }
  };

  const cardsById = useMemo(() => board?.cards ?? {}, [board]);

  const handleDragStart = (event: DragStartEvent) => {
    setActiveCardId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveCardId(null);

    if (!board || !over || active.id === over.id) {
      return;
    }

    const activeCardId = active.id as string;
    const target = getMoveTarget(board, activeCardId, over.id as string);
    if (!target) {
      return;
    }

    void applyMutation(() => moveCard(activeCardId, target.columnId, target.position));
  };

  const handleRenameColumn = (columnId: string, title: string) => {
    void applyMutation(() => renameColumn(columnId, title));
  };

  const handleAddCard = (columnId: string, title: string, details: string) => {
    void applyMutation(() => createCard(columnId, title, details));
  };

  const handleDeleteCard = (_columnId: string, cardId: string) => {
    void applyMutation(() => deleteCard(cardId));
  };

  const activeCard = activeCardId ? cardsById[activeCardId] : null;

  const handleSubmitChat = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const prompt = chatInput.trim();
    if (!prompt || isChatSubmitting) {
      return;
    }

    setIsChatSubmitting(true);
    setChatError(null);
    setChatMessages((prev) => [...prev, { role: "user", content: prompt }]);
    setChatInput("");

    try {
      const response = await chatWithAssistant(prompt);
      setChatMessages((prev) => [...prev, response.assistant]);
      setBoard(response.board);
      if (response.operationErrors.length > 0) {
        setChatError(response.operationErrors.join(" "));
      } else {
        setChatError(null);
      }
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to send message.";
      setChatError(message);
    } finally {
      setIsChatSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <main className="grid min-h-screen place-items-center px-6">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
          Loading board...
        </p>
      </main>
    );
  }

  if (!board) {
    return (
      <main className="grid min-h-screen place-items-center px-6">
        <div className="w-full max-w-lg rounded-3xl border border-[var(--stroke)] bg-white p-8 text-center shadow-[var(--shadow)]">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
            Unable to load board
          </p>
          <p className="mt-3 text-sm text-[var(--gray-text)]">{error ?? "Unknown error."}</p>
          <button
            type="button"
            onClick={() => void loadBoard()}
            className="mt-6 rounded-full bg-[var(--secondary-purple)] px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white transition hover:brightness-110"
          >
            Retry
          </button>
        </div>
      </main>
    );
  }

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-[1500px] flex-col gap-10 px-6 pb-16 pt-12">
        <header className="flex flex-col gap-6 rounded-[32px] border border-[var(--stroke)] bg-white/80 p-8 shadow-[var(--shadow)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                Single Board Kanban
              </p>
              <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy-dark)]">
                Kanban Studio
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--gray-text)]">
                Keep momentum visible. Rename columns, drag cards between stages,
                and capture quick notes without getting buried in settings.
              </p>
            </div>
            <div className="flex items-start gap-3">
              <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-5 py-4">
                <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                  Focus
                </p>
                <p className="mt-2 text-lg font-semibold text-[var(--primary-blue)]">
                  One board. Five columns. Zero clutter.
                </p>
              </div>
              <button
                type="button"
                onClick={() => onLogout?.()}
                className="rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)] transition hover:text-[var(--navy-dark)]"
                aria-label="Log out"
                hidden={!onLogout}
              >
                Log out
              </button>
            </div>
          </div>

          {error ? (
            <div className="rounded-2xl border border-[var(--stroke)] bg-white px-4 py-3">
              <p className="text-sm text-[var(--secondary-purple)]">{error}</p>
            </div>
          ) : null}

          <div className="flex flex-wrap items-center gap-4">
            {board.columns.map((column) => (
              <div
                key={column.id}
                className="flex items-center gap-2 rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)]"
              >
                <span className="h-2 w-2 rounded-full bg-[var(--accent-yellow)]" />
                {column.title}
              </div>
            ))}
          </div>
        </header>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
          <DndContext
            sensors={sensors}
            collisionDetection={closestCorners}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <section className="grid gap-6 lg:grid-cols-3 2xl:grid-cols-5">
              {board.columns.map((column) => (
                <KanbanColumn
                  key={column.id}
                  column={column}
                  cards={column.cardIds.map((cardId) => board.cards[cardId]).filter(Boolean)}
                  onRename={handleRenameColumn}
                  onAddCard={handleAddCard}
                  onDeleteCard={handleDeleteCard}
                />
              ))}
            </section>
            <DragOverlay>
              {activeCard ? (
                <div className="w-[260px]">
                  <KanbanCardPreview card={activeCard} />
                </div>
              ) : null}
            </DragOverlay>
          </DndContext>

          <aside className="flex min-h-[420px] flex-col rounded-[28px] border border-[var(--stroke)] bg-white/90 p-5 shadow-[var(--shadow)] backdrop-blur">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                AI Assistant
              </p>
              <h2 className="mt-2 font-display text-2xl text-[var(--navy-dark)]">Board Copilot</h2>
              <p className="mt-2 text-sm text-[var(--gray-text)]">
                Ask to create, edit, or move cards.
              </p>
            </div>

            <div className="mt-4 flex-1 space-y-3 overflow-y-auto rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] p-3">
              {chatMessages.length === 0 ? (
                <p className="text-sm text-[var(--gray-text)]">No messages yet.</p>
              ) : (
                chatMessages.map((message, index) => (
                  <div
                    key={`${message.role}-${index}`}
                    data-testid={`chat-message-${index}`}
                    className={
                      message.role === "user"
                        ? "ml-auto max-w-[90%] rounded-2xl bg-[var(--secondary-purple)] px-3 py-2 text-sm text-white"
                        : "mr-auto max-w-[90%] rounded-2xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm text-[var(--navy-dark)]"
                    }
                  >
                    <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.18em] opacity-70">
                      {message.role === "user" ? "You" : "Assistant"}
                    </p>
                    <p>{message.content}</p>
                  </div>
                ))
              )}
            </div>

            {chatError ? (
              <p role="alert" className="mt-3 text-sm text-[var(--secondary-purple)]">
                {chatError}
              </p>
            ) : null}

            <form className="mt-4 flex gap-2" onSubmit={handleSubmitChat}>
              <label className="sr-only" htmlFor="ai-chat-input">
                AI message
              </label>
              <input
                id="ai-chat-input"
                value={chatInput}
                onChange={(event) => setChatInput(event.target.value)}
                placeholder="Ask AI to update your board..."
                className="min-w-0 flex-1 rounded-full border border-[var(--stroke)] bg-white px-4 py-2 text-sm text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
              />
              <button
                type="submit"
                disabled={isChatSubmitting || !chatInput.trim()}
                className="rounded-full bg-[var(--secondary-purple)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-70"
              >
                {isChatSubmitting ? "Sending..." : "Send"}
              </button>
            </form>
          </aside>
        </div>
      </main>
    </div>
  );
};
