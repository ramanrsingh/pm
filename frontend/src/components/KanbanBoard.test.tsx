import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KanbanBoard } from "@/components/KanbanBoard";
import { initialData, type BoardData } from "@/lib/kanban";

const cloneBoard = (): BoardData => {
  return {
    columns: initialData.columns.map((column) => ({
      ...column,
      cardIds: [...column.cardIds],
    })),
    cards: Object.fromEntries(
      Object.entries(initialData.cards).map(([id, card]) => [id, { ...card }])
    ),
  };
};

const makeResponse = (board: BoardData, status = 200) => {
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

    if (url.endsWith("/api/board") && (!init?.method || init.method === "GET")) {
      return makeResponse(board);
    }

    if (url.includes("/api/columns/") && init?.method === "PATCH") {
      const columnId = url.split("/api/columns/")[1];
      const payload = JSON.parse(String(init.body)) as { title: string };
      board.columns = board.columns.map((column) =>
        column.id === columnId ? { ...column, title: payload.title } : column
      );
      return makeResponse(board);
    }

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
      return makeResponse(board);
    }

    if (url.includes("/api/cards/") && init?.method === "DELETE") {
      const cardId = url.split("/api/cards/")[1];
      delete board.cards[cardId];
      board.columns = board.columns.map((column) => ({
        ...column,
        cardIds: column.cardIds.filter((id) => id !== cardId),
      }));
      return makeResponse(board);
    }

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
          model: "openai/gpt-oss-120b:free",
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
    expect(screen.getAllByTestId(/column-/i)).toHaveLength(5);
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
    const chatInput = screen.getByPlaceholderText(/ask ai to update your board/i);
    await userEvent.type(chatInput, "new backlog task");
    await userEvent.click(screen.getByRole("button", { name: /^send$/i }));

    expect(await screen.findByText("Done.")).toBeInTheDocument();
    expect(within(column).getByText("AI new backlog task")).toBeInTheDocument();
  });
});
