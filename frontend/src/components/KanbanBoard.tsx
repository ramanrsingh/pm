"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
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
  addColumn,
  chatWithAssistant,
  createCard,
  createBoard,
  deleteBoard,
  deleteCard,
  fetchBoardById,
  fetchBoards,
  moveCard,
  renameColumn,
  type AIChatMessage,
  type BoardSummary,
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
  const [boards, setBoards] = useState<BoardSummary[]>([]);
  const [activeBoardId, setActiveBoardId] = useState<string | null>(null);
  const [board, setBoard] = useState<BoardData | null>(null);
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<AIChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatError, setChatError] = useState<string | null>(null);
  const [isChatSubmitting, setIsChatSubmitting] = useState(false);
  const [showNewBoardForm, setShowNewBoardForm] = useState(false);
  const [newBoardName, setNewBoardName] = useState("");
  const [isCreatingBoard, setIsCreatingBoard] = useState(false);
  const [showAddColumn, setShowAddColumn] = useState(false);
  const [newColumnTitle, setNewColumnTitle] = useState("");
  const chatEndRef = useRef<HTMLDivElement>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    })
  );

  const loadBoards = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const boardList = await fetchBoards();
      setBoards(boardList);
      if (boardList.length > 0) {
        const targetId = activeBoardId && boardList.some((b) => b.id === activeBoardId)
          ? activeBoardId
          : boardList[0].id;
        setActiveBoardId(targetId);
        const boardData = await fetchBoardById(targetId);
        setBoard(boardData);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to load boards.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  const switchBoard = async (boardId: string) => {
    if (boardId === activeBoardId) return;
    setIsLoading(true);
    setError(null);
    setChatMessages([]);
    try {
      const boardData = await fetchBoardById(boardId);
      setActiveBoardId(boardId);
      setBoard(boardData);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to load board.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void loadBoards(); }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

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

    const draggedCardId = active.id as string;
    const target = getMoveTarget(board, draggedCardId, over.id as string);
    if (!target) {
      return;
    }

    void applyMutation(() => moveCard(draggedCardId, target.columnId, target.position, activeBoardId ?? undefined));
  };

  const handleRenameColumn = (columnId: string, title: string) => {
    void applyMutation(() => renameColumn(columnId, title, activeBoardId ?? undefined));
  };

  const handleAddCard = (columnId: string, title: string, details: string) => {
    void applyMutation(() => createCard(columnId, title, details, activeBoardId ?? undefined));
  };

  const handleDeleteCard = (_columnId: string, cardId: string) => {
    void applyMutation(() => deleteCard(cardId, activeBoardId ?? undefined));
  };

  const handleCreateBoard = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const name = newBoardName.trim();
    if (!name || isCreatingBoard) return;
    setIsCreatingBoard(true);
    try {
      const newBoard = await createBoard(name);
      const newSummary: BoardSummary = {
        id: newBoard.id!,
        name: newBoard.name!,
        createdAt: new Date().toISOString(),
      };
      setBoards((prev) => [...prev, newSummary]);
      setActiveBoardId(newBoard.id!);
      setBoard(newBoard);
      setChatMessages([]);
      setNewBoardName("");
      setShowNewBoardForm(false);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to create board.";
      setError(message);
    } finally {
      setIsCreatingBoard(false);
    }
  };

  const handleDeleteBoard = async () => {
    if (!activeBoardId || boards.length <= 1) return;
    if (!confirm("Delete this board and all its cards?")) return;
    try {
      await deleteBoard(activeBoardId);
      const remaining = boards.filter((b) => b.id !== activeBoardId);
      setBoards(remaining);
      if (remaining.length > 0) {
        await switchBoard(remaining[0].id);
      } else {
        setBoard(null);
        setActiveBoardId(null);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to delete board.";
      setError(message);
    }
  };

  const handleAddColumn = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const title = newColumnTitle.trim();
    if (!title || !activeBoardId) return;
    await applyMutation(() => addColumn(activeBoardId, title));
    setNewColumnTitle("");
    setShowAddColumn(false);
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
      const response = await chatWithAssistant(prompt, activeBoardId ?? undefined);
      setChatMessages((prev) => [...prev, response.assistant]);
      if (response.board) {
        setBoard(response.board);
      }
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
        <div className="flex flex-col items-center gap-4">
          <div className="animate-spin-smooth h-8 w-8 rounded-full border-2 border-[var(--stroke)] border-t-[var(--primary-blue)]" />
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
            Loading board
          </p>
        </div>
      </main>
    );
  }

  if (!board) {
    return (
      <main className="grid min-h-screen place-items-center px-6">
        <div className="w-full max-w-lg rounded-3xl border border-[var(--stroke)] bg-white p-8 text-center shadow-[var(--shadow-lg)]">
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
            Unable to load board
          </p>
          <p className="mt-3 text-sm text-[var(--gray-text)]">{error ?? "Unknown error."}</p>
          <button
            type="button"
            onClick={() => void loadBoards()}
            className="mt-6 rounded-full bg-[var(--secondary-purple)] px-5 py-2.5 text-xs font-semibold uppercase tracking-wide text-white transition hover:brightness-110"
          >
            Retry
          </button>
        </div>
      </main>
    );
  }

  return (
    <div className="relative overflow-hidden">
      {/* Background decorative gradients */}
      <div className="pointer-events-none absolute left-0 top-0 h-[500px] w-[500px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.22)_0%,_rgba(32,157,215,0.04)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[600px] w-[600px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.16)_0%,_rgba(117,57,145,0.04)_55%,_transparent_75%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-[1600px] flex-col gap-8 px-6 pb-16 pt-10">
        {/* Header */}
        <header className="flex flex-col gap-5 rounded-[28px] border border-[var(--stroke)] bg-white/80 px-8 py-6 shadow-[var(--shadow)] backdrop-blur">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              {/* Logo mark */}
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-[var(--navy-dark)]">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                  <rect x="2" y="2" width="7" height="10" rx="1.5" fill="white" opacity="0.9" />
                  <rect x="11" y="2" width="7" height="6" rx="1.5" fill="white" opacity="0.5" />
                  <rect x="11" y="10" width="7" height="8" rx="1.5" fill="white" opacity="0.7" />
                  <rect x="2" y="14" width="7" height="4" rx="1.5" fill="white" opacity="0.5" />
                </svg>
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                  Workspace
                </p>
                <h1 className="font-display text-2xl font-semibold leading-tight text-[var(--navy-dark)]">
                  Kanban Studio
                </h1>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {onLogout && (
                <button
                  type="button"
                  onClick={() => onLogout()}
                  className="rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)] transition-all duration-150 hover:border-[var(--navy-dark)]/20 hover:text-[var(--navy-dark)]"
                  aria-label="Log out"
                >
                  Log out
                </button>
              )}
            </div>
          </div>

          {/* Board tabs */}
          <div className="flex flex-wrap items-center gap-2">
            {boards.map((b) => (
              <button
                key={b.id}
                type="button"
                onClick={() => void switchBoard(b.id)}
                data-testid={`board-tab-${b.id}`}
                className={`rounded-full border px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.15em] transition-all duration-150 ${
                  b.id === activeBoardId
                    ? "border-[var(--primary-blue)] bg-[var(--primary-blue)] text-white"
                    : "border-[var(--stroke)] bg-[var(--surface)] text-[var(--navy-dark)] hover:border-[var(--primary-blue)]/40"
                }`}
              >
                {b.name}
              </button>
            ))}

            {/* New board button / form */}
            {showNewBoardForm ? (
              <form
                onSubmit={handleCreateBoard}
                className="flex items-center gap-2"
              >
                <input
                  autoFocus
                  value={newBoardName}
                  onChange={(e) => setNewBoardName(e.target.value)}
                  placeholder="Board name"
                  className="rounded-xl border border-[var(--stroke)] bg-white px-3 py-1.5 text-xs text-[var(--navy-dark)] outline-none focus:border-[var(--primary-blue)]"
                />
                <button
                  type="submit"
                  disabled={isCreatingBoard || !newBoardName.trim()}
                  className="rounded-full bg-[var(--primary-blue)] px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                >
                  Create
                </button>
                <button
                  type="button"
                  onClick={() => { setShowNewBoardForm(false); setNewBoardName(""); }}
                  className="rounded-full border border-[var(--stroke)] px-3 py-1.5 text-xs text-[var(--gray-text)]"
                >
                  Cancel
                </button>
              </form>
            ) : (
              <button
                type="button"
                onClick={() => setShowNewBoardForm(true)}
                data-testid="new-board-button"
                className="rounded-full border border-dashed border-[var(--stroke)] px-3 py-1.5 text-xs text-[var(--gray-text)] transition hover:border-[var(--primary-blue)] hover:text-[var(--primary-blue)]"
              >
                + New board
              </button>
            )}

            {/* Delete current board (only shown when multiple boards exist) */}
            {boards.length > 1 && activeBoardId && (
              <button
                type="button"
                onClick={handleDeleteBoard}
                data-testid="delete-board-button"
                className="ml-auto rounded-full border border-red-200 px-3 py-1.5 text-xs text-red-400 transition hover:border-red-400 hover:text-red-600"
              >
                Delete board
              </button>
            )}
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-xl border border-red-100 bg-red-50 px-4 py-2.5">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                <circle cx="7" cy="7" r="6" stroke="#f87171" strokeWidth="1.5" />
                <path d="M7 4v3.5M7 9.5v.5" stroke="#f87171" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              <p className="text-xs font-medium text-red-500">{error}</p>
            </div>
          )}
        </header>

        {/* Board + Sidebar */}
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
          <DndContext
            sensors={sensors}
            collisionDetection={closestCorners}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <div className="flex flex-col gap-4">
              <section className="grid gap-5 lg:grid-cols-3 2xl:grid-cols-5">
                {board.columns.map((column, index) => (
                  <KanbanColumn
                    key={column.id}
                    column={column}
                    cards={column.cardIds.map((cardId) => board.cards[cardId]).filter(Boolean)}
                    index={index}
                    onRename={handleRenameColumn}
                    onAddCard={handleAddCard}
                    onDeleteCard={handleDeleteCard}
                  />
                ))}
              </section>

              {/* Add column */}
              <div className="flex items-center gap-3 pt-2">
                {showAddColumn ? (
                  <form onSubmit={handleAddColumn} className="flex items-center gap-2">
                    <input
                      autoFocus
                      value={newColumnTitle}
                      onChange={(e) => setNewColumnTitle(e.target.value)}
                      placeholder="Column title"
                      className="rounded-xl border border-[var(--stroke)] bg-white px-3 py-1.5 text-xs text-[var(--navy-dark)] outline-none focus:border-[var(--primary-blue)]"
                    />
                    <button
                      type="submit"
                      disabled={!newColumnTitle.trim()}
                      className="rounded-full bg-[var(--primary-blue)] px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                    >
                      Add
                    </button>
                    <button
                      type="button"
                      onClick={() => { setShowAddColumn(false); setNewColumnTitle(""); }}
                      className="rounded-full border border-[var(--stroke)] px-3 py-1.5 text-xs text-[var(--gray-text)]"
                    >
                      Cancel
                    </button>
                  </form>
                ) : (
                  <button
                    type="button"
                    onClick={() => setShowAddColumn(true)}
                    data-testid="add-column-button"
                    className="rounded-full border border-dashed border-[var(--stroke)] px-4 py-2 text-xs text-[var(--gray-text)] transition hover:border-[var(--primary-blue)] hover:text-[var(--primary-blue)]"
                  >
                    + Add column
                  </button>
                )}
              </div>
            </div>
            <DragOverlay dropAnimation={{ duration: 180, easing: "cubic-bezier(0.25, 1, 0.5, 1)" }}>
              {activeCard ? (
                <div className="w-[260px]">
                  <KanbanCardPreview card={activeCard} />
                </div>
              ) : null}
            </DragOverlay>
          </DndContext>

          {/* AI Chat Sidebar */}
          <aside className="flex min-h-[480px] flex-col rounded-[24px] border border-[var(--stroke)] bg-white/90 shadow-[var(--shadow)] backdrop-blur">
            {/* Sidebar header */}
            <div className="border-b border-[var(--stroke)] px-5 py-4">
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[var(--secondary-purple)]">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                    <path
                      d="M8 2C4.69 2 2 4.69 2 8c0 1.04.27 2.02.74 2.87L2 14l3.13-.74C5.98 13.73 6.96 14 8 14c3.31 0 6-2.69 6-6s-2.69-6-6-6z"
                      fill="white"
                      opacity="0.9"
                    />
                  </svg>
                </div>
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                    AI Assistant
                  </p>
                  <h2 className="font-display text-base font-semibold text-[var(--navy-dark)]">
                    Board Copilot
                  </h2>
                </div>
              </div>
            </div>

            {/* Messages */}
            <div className="chat-messages flex-1 space-y-3 overflow-y-auto px-4 py-4">
              {chatMessages.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
                  <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[var(--surface)]">
                    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
                      <path
                        d="M9 2C5.13 2 2 5.13 2 9c0 1.22.31 2.37.86 3.37L2 16l3.63-.86C6.63 15.69 7.78 16 9 16c3.87 0 7-3.13 7-7s-3.13-7-7-7z"
                        stroke="var(--gray-text)"
                        strokeWidth="1.2"
                        fill="none"
                      />
                      <path
                        d="M6 9h6M6 6.5h4"
                        stroke="var(--gray-text)"
                        strokeWidth="1.2"
                        strokeLinecap="round"
                      />
                    </svg>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-[var(--navy-dark)]">
                      Ask anything
                    </p>
                    <p className="mt-1 text-xs text-[var(--gray-text)]">
                      Create, move, or edit cards with a prompt.
                    </p>
                  </div>
                </div>
              ) : (
                chatMessages.map((message, index) => (
                  <div
                    key={`${message.role}-${index}`}
                    data-testid={`chat-message-${message.role}-${index}`}
                    className={
                      message.role === "user"
                        ? "animate-fade-in ml-6 rounded-2xl rounded-tr-sm bg-[var(--secondary-purple)] px-3.5 py-2.5 text-sm text-white"
                        : "animate-fade-in mr-6 rounded-2xl rounded-tl-sm border border-[var(--stroke)] bg-white px-3.5 py-2.5 text-sm text-[var(--navy-dark)]"
                    }
                  >
                    <p className="mb-1 text-[9px] font-bold uppercase tracking-[0.2em] opacity-60">
                      {message.role === "user" ? "You" : "Copilot"}
                    </p>
                    <p className="leading-relaxed">{message.content}</p>
                  </div>
                ))
              )}
              {isChatSubmitting && (
                <div className="animate-fade-in mr-6 flex items-center gap-2 rounded-2xl rounded-tl-sm border border-[var(--stroke)] bg-white px-3.5 py-3">
                  <div className="flex gap-1">
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--gray-text)] [animation-delay:0ms]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--gray-text)] [animation-delay:150ms]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--gray-text)] [animation-delay:300ms]" />
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {chatError && (
              <div className="mx-4 mb-2 rounded-xl border border-[var(--secondary-purple)]/20 bg-[rgba(117,57,145,0.05)] px-3 py-2">
                <p role="alert" className="text-xs text-[var(--secondary-purple)]">
                  {chatError}
                </p>
              </div>
            )}

            {/* Input */}
            <div className="border-t border-[var(--stroke)] px-4 py-3">
              <form className="flex gap-2" onSubmit={handleSubmitChat}>
                <label className="sr-only" htmlFor="ai-chat-input">
                  AI message
                </label>
                <input
                  id="ai-chat-input"
                  value={chatInput}
                  onChange={(event) => setChatInput(event.target.value)}
                  placeholder="Ask to update your board..."
                  disabled={isChatSubmitting}
                  className="min-w-0 flex-1 rounded-full border border-[var(--stroke)] bg-[var(--surface)] px-4 py-2 text-sm text-[var(--navy-dark)] outline-none transition-colors duration-150 focus:border-[var(--primary-blue)] focus:bg-white disabled:opacity-50"
                />
                <button
                  type="submit"
                  disabled={isChatSubmitting || !chatInput.trim()}
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--secondary-purple)] text-white transition-all duration-150 hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
                  aria-label="Send message"
                >
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                    <path
                      d="M13 7L1 1l3 6-3 6 12-6z"
                      fill="currentColor"
                    />
                  </svg>
                </button>
              </form>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
};
