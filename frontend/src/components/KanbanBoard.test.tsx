import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KanbanBoard } from "@/components/KanbanBoard";
import { type BoardData } from "@/lib/kanban";

const BOARD_ID = "board-1";

// Fixture data for tests — mirrors the backend seed data.
const initialData: BoardData = {
  id: BOARD_ID,
  name: "Project Board",
  columns: [
    { id: "col-backlog", title: "Backlog", cardIds: ["card-1", "card-2"] },
    { id: "col-discovery", title: "Discovery", cardIds: ["card-3"] },
    {
      id: "col-progress",
      title: "In Progress",
      cardIds: ["card-4", "card-5"],
    },
    { id: "col-review", title: "Review", cardIds: ["card-6"] },
    { id: "col-done", title: "Done", cardIds: ["card-7", "card-8"] },
  ],
  cards: {
    "card-1": {
      id: "card-1",
      title: "Align roadmap themes",
      details: "Draft quarterly themes with impact statements and metrics.",
    },
    "card-2": {
      id: "card-2",
      title: "Gather customer signals",
      details: "Review support tags, sales notes, and churn feedback.",
    },
    "card-3": {
      id: "card-3",
      title: "Prototype analytics view",
      details: "Sketch initial dashboard layout and key drill-downs.",
    },
    "card-4": {
      id: "card-4",
      title: "Refine status language",
      details: "Standardize column labels and tone across the board.",
    },
    "card-5": {
      id: "card-5",
      title: "Design card layout",
      details: "Add hierarchy and spacing for scanning dense lists.",
    },
    "card-6": {
      id: "card-6",
      title: "QA micro-interactions",
      details: "Verify hover, focus, and loading states.",
    },
    "card-7": {
      id: "card-7",
      title: "Ship marketing page",
      details: "Final copy approved and asset pack delivered.",
    },
    "card-8": {
      id: "card-8",
      title: "Close onboarding sprint",
      details: "Document release notes and share internally.",
    },
  },
};

const cloneBoard = (): BoardData => {
  return {
    id: initialData.id,
    name: initialData.name,
    columns: initialData.columns.map((column) => ({
      ...column,
      cardIds: [...column.cardIds],
    })),
    cards: Object.fromEntries(
      Object.entries(initialData.cards).map(([id, card]) => [id, { ...card }])
    ),
  };
};

const makeBoardResponse = (board: BoardData, status = 200) => {
  return new Response(JSON.stringify({ board }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
};

const setupBoardFetchMock = () => {
  const board = cloneBoard();
  let aiCardCounter = 0;

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    // Board list
    if (url.endsWith("/api/boards") && (!init?.method || init.method === "GET")) {
      return new Response(
        JSON.stringify({
          boards: [{ id: BOARD_ID, name: "Project Board", createdAt: "2024-01-01T00:00:00" }],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    // Specific board by id
    if (url.endsWith(`/api/boards/${BOARD_ID}`) && (!init?.method || init.method === "GET")) {
      return makeBoardResponse(board);
    }

    // Legacy board endpoint
    if (url.endsWith("/api/board") && (!init?.method || init.method === "GET")) {
      return makeBoardResponse(board);
    }

    // Column rename (board-scoped)
    if (url.includes(`/api/boards/${BOARD_ID}/columns/`) && init?.method === "PATCH") {
      const columnId = url.split(`/api/boards/${BOARD_ID}/columns/`)[1];
      const payload = JSON.parse(String(init.body)) as { title: string };
      board.columns = board.columns.map((column) =>
        column.id === columnId ? { ...column, title: payload.title } : column
      );
      return makeBoardResponse(board);
    }

    // Legacy column rename
    if (url.includes("/api/columns/") && init?.method === "PATCH") {
      const columnId = url.split("/api/columns/")[1];
      const payload = JSON.parse(String(init.body)) as { title: string };
      board.columns = board.columns.map((column) =>
        column.id === columnId ? { ...column, title: payload.title } : column
      );
      return makeBoardResponse(board);
    }

    // Card create (board-scoped)
    if (url.endsWith(`/api/boards/${BOARD_ID}/cards`) && init?.method === "POST") {
      const payload = JSON.parse(String(init.body)) as {
        columnId: string;
        title: string;
        details: string;
      };
      const cardId = "card-new";
      board.cards[cardId] = {
        id: cardId,
        title: payload.title,
        details: payload.details,
      };
      board.columns = board.columns.map((column) =>
        column.id === payload.columnId
          ? { ...column, cardIds: [...column.cardIds, cardId] }
          : column
      );
      return makeBoardResponse(board);
    }

    // Legacy card create
    if (url.endsWith("/api/cards") && init?.method === "POST") {
      const payload = JSON.parse(String(init.body)) as {
        columnId: string;
        title: string;
        details: string;
      };
      const cardId = "card-new";
      board.cards[cardId] = {
        id: cardId,
        title: payload.title,
        details: payload.details,
      };
      board.columns = board.columns.map((column) =>
        column.id === payload.columnId
          ? { ...column, cardIds: [...column.cardIds, cardId] }
          : column
      );
      return makeBoardResponse(board);
    }

    // Card delete (board-scoped)
    if (url.includes(`/api/boards/${BOARD_ID}/cards/`) && init?.method === "DELETE") {
      const cardId = url.split(`/api/boards/${BOARD_ID}/cards/`)[1];
      delete board.cards[cardId];
      board.columns = board.columns.map((column) => ({
        ...column,
        cardIds: column.cardIds.filter((id) => id !== cardId),
      }));
      return makeBoardResponse(board);
    }

    // Legacy card delete
    if (url.includes("/api/cards/") && init?.method === "DELETE") {
      const cardId = url.split("/api/cards/")[1];
      delete board.cards[cardId];
      board.columns = board.columns.map((column) => ({
        ...column,
        cardIds: column.cardIds.filter((id) => id !== cardId),
      }));
      return makeBoardResponse(board);
    }

    // Board-scoped AI chat
    if (url.endsWith(`/api/boards/${BOARD_ID}/chat`) && init?.method === "POST") {
      const payload = JSON.parse(String(init.body)) as { prompt: string };
      aiCardCounter += 1;
      const cardId = `card-ai-${aiCardCounter}`;
      board.cards[cardId] = {
        id: cardId,
        title: `AI ${payload.prompt}`,
        details: "Generated",
      };
      board.columns = board.columns.map((column) =>
        column.id === "col-backlog"
          ? { ...column, cardIds: [...column.cardIds, cardId] }
          : column
      );

      return new Response(
        JSON.stringify({
          assistant: { role: "assistant", content: "Done." },
          parsed: true,
          boardUpdated: true,
          appliedOperations: [{ index: 0, type: "create_card" }],
          operationErrors: [],
          board,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    // Legacy AI chat
    if (url.endsWith("/api/ai/chat") && init?.method === "POST") {
      const payload = JSON.parse(String(init.body)) as { prompt: string };
      aiCardCounter += 1;
      const cardId = `card-ai-${aiCardCounter}`;
      board.cards[cardId] = {
        id: cardId,
        title: `AI ${payload.prompt}`,
        details: "Generated",
      };
      board.columns = board.columns.map((column) =>
        column.id === "col-backlog"
          ? { ...column, cardIds: [...column.cardIds, cardId] }
          : column
      );

      return new Response(
        JSON.stringify({
          assistant: { role: "assistant", content: "Done." },
          parsed: true,
          boardUpdated: true,
          appliedOperations: [{ index: 0, type: "create_card" }],
          operationErrors: [],
          board,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    throw new Error(`Unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
};

describe("KanbanBoard", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders five columns from backend", async () => {
    setupBoardFetchMock();

    render(<KanbanBoard />);

    expect(await screen.findByTestId("column-col-backlog")).toBeInTheDocument();
    // Match only column-col-* testids, not add-column-button.
    expect(screen.getAllByTestId(/^column-col-/i)).toHaveLength(5);
  });

  it("shows board tabs for all boards", async () => {
    setupBoardFetchMock();

    render(<KanbanBoard />);

    await screen.findByTestId("column-col-backlog");
    expect(screen.getByTestId(`board-tab-${BOARD_ID}`)).toBeInTheDocument();
    expect(screen.getByTestId(`board-tab-${BOARD_ID}`)).toHaveTextContent("Project Board");
  });

  it("shows new board button", async () => {
    setupBoardFetchMock();

    render(<KanbanBoard />);

    await screen.findByTestId("column-col-backlog");
    expect(screen.getByTestId("new-board-button")).toBeInTheDocument();
  });

  it("shows add column button", async () => {
    setupBoardFetchMock();

    render(<KanbanBoard />);

    await screen.findByTestId("column-col-backlog");
    expect(screen.getByTestId("add-column-button")).toBeInTheDocument();
  });

  it("renames a column via backend", async () => {
    setupBoardFetchMock();

    render(<KanbanBoard />);

    const column = await screen.findByTestId("column-col-backlog");
    const input = within(column).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "Ideas");

    await waitFor(() => {
      expect(input).toHaveValue("Ideas");
    });
  });

  it("adds and removes a card via backend", async () => {
    setupBoardFetchMock();

    render(<KanbanBoard />);

    const column = await screen.findByTestId("column-col-backlog");
    const addButton = within(column).getByRole("button", {
      name: /add a card/i,
    });
    await userEvent.click(addButton);

    const titleInput = within(column).getByPlaceholderText(/card title/i);
    await userEvent.type(titleInput, "New card");
    const detailsInput = within(column).getByPlaceholderText(/details/i);
    await userEvent.type(detailsInput, "Notes");

    await userEvent.click(within(column).getByRole("button", { name: /add card/i }));

    expect(await within(column).findByText("New card")).toBeInTheDocument();

    const deleteButton = within(column).getByRole("button", {
      name: /delete new card/i,
    });
    await userEvent.click(deleteButton);

    await waitFor(() => {
      expect(within(column).queryByText("New card")).not.toBeInTheDocument();
    });
  });

  it("sends AI chat message and refreshes board state from response", async () => {
    setupBoardFetchMock();

    render(<KanbanBoard />);

    const column = await screen.findByTestId("column-col-backlog");
    const chatInput = screen.getByPlaceholderText(/ask.*to update your board/i);
    await userEvent.type(chatInput, "new backlog task");
    await userEvent.click(screen.getByRole("button", { name: /send message/i }));

    expect(await screen.findByText("Done.")).toBeInTheDocument();
    expect(within(column).getByText("AI new backlog task")).toBeInTheDocument();
  });
});
