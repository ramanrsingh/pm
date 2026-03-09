import { expect, test, type Page, type Route } from "@playwright/test";

type Card = {
  id: string;
  title: string;
  details: string;
  metadata: Record<string, never>;
};

type Board = {
  columns: Array<{ id: string; title: string; cardIds: string[] }>;
  cards: Record<string, Card>;
};

const createBoard = (): Board => ({
  columns: [
    { id: "col-backlog", title: "Backlog", cardIds: ["card-1", "card-2"] },
    { id: "col-discovery", title: "Discovery", cardIds: ["card-3"] },
    { id: "col-progress", title: "In Progress", cardIds: ["card-4", "card-5"] },
    { id: "col-review", title: "Review", cardIds: ["card-6"] },
    { id: "col-done", title: "Done", cardIds: ["card-7", "card-8"] },
  ],
  cards: {
    "card-1": {
      id: "card-1",
      title: "Align roadmap themes",
      details: "Draft quarterly themes with impact statements and metrics.",
      metadata: {},
    },
    "card-2": {
      id: "card-2",
      title: "Gather customer signals",
      details: "Review support tags, sales notes, and churn feedback.",
      metadata: {},
    },
    "card-3": {
      id: "card-3",
      title: "Prototype analytics view",
      details: "Sketch initial dashboard layout and key drill-downs.",
      metadata: {},
    },
    "card-4": {
      id: "card-4",
      title: "Refine status language",
      details: "Standardize column labels and tone across the board.",
      metadata: {},
    },
    "card-5": {
      id: "card-5",
      title: "Design card layout",
      details: "Add hierarchy and spacing for scanning dense lists.",
      metadata: {},
    },
    "card-6": {
      id: "card-6",
      title: "QA micro-interactions",
      details: "Verify hover, focus, and loading states.",
      metadata: {},
    },
    "card-7": {
      id: "card-7",
      title: "Ship marketing page",
      details: "Final copy approved and asset pack delivered.",
      metadata: {},
    },
    "card-8": {
      id: "card-8",
      title: "Close onboarding sprint",
      details: "Document release notes and share internally.",
      metadata: {},
    },
  },
});

const mockApi = async (page: Page) => {
  let sessionActive = false;
  const board = createBoard();
  let createdCardIndex = 0;

  const fulfill = async (route: Route, payload: unknown, status = 200) => {
    await route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(payload),
    });
  };

  await page.route("**/api/auth/me", async (route) => {
    if (sessionActive) {
      await fulfill(route, { status: "authenticated", username: "user" });
      return;
    }
    await fulfill(route, { detail: "Not authenticated." }, 401);
  });

  await page.route("**/api/auth/login", async (route) => {
    const payload = route.request().postDataJSON() as { username?: string; password?: string };
    if (payload.username === "user" && payload.password === "password") {
      sessionActive = true;
      await fulfill(route, { status: "ok" });
      return;
    }
    await fulfill(route, { detail: "Invalid username or password." }, 401);
  });

  await page.route("**/api/auth/logout", async (route) => {
    sessionActive = false;
    await fulfill(route, { status: "ok" });
  });

  await page.route("**/api/board", async (route) => {
    if (!sessionActive) {
      await fulfill(route, { detail: "Not authenticated." }, 401);
      return;
    }
    await fulfill(route, { board });
  });

  await page.route("**/api/columns/*", async (route) => {
    if (!sessionActive) {
      await fulfill(route, { detail: "Not authenticated." }, 401);
      return;
    }

    const url = new URL(route.request().url());
    const columnId = url.pathname.split("/api/columns/")[1];
    const payload = route.request().postDataJSON() as { title: string };

    board.columns = board.columns.map((column) =>
      column.id === columnId ? { ...column, title: payload.title } : column
    );

    await fulfill(route, { board });
  });

  await page.route("**/api/cards/*/move", async (route) => {
    if (!sessionActive) {
      await fulfill(route, { detail: "Not authenticated." }, 401);
      return;
    }

    const url = new URL(route.request().url());
    const cardId = url.pathname.split("/api/cards/")[1].split("/move")[0];
    const payload = route.request().postDataJSON() as {
      columnId: string;
      position: number | null;
    };

    const sourceColumn = board.columns.find((column) => column.cardIds.includes(cardId));
    const destinationColumn = board.columns.find((column) => column.id === payload.columnId);

    if (!sourceColumn || !destinationColumn) {
      await fulfill(route, { detail: "Card or column not found." }, 404);
      return;
    }

    sourceColumn.cardIds = sourceColumn.cardIds.filter((id) => id !== cardId);
    const destinationIndex =
      payload.position === null || payload.position > destinationColumn.cardIds.length
        ? destinationColumn.cardIds.length
        : Math.max(0, payload.position);
    destinationColumn.cardIds.splice(destinationIndex, 0, cardId);

    await fulfill(route, { board });
  });

  await page.route("**/api/cards/*", async (route) => {
    if (!sessionActive) {
      await fulfill(route, { detail: "Not authenticated." }, 401);
      return;
    }

    if (route.request().method() !== "DELETE") {
      await route.fallback();
      return;
    }

    const url = new URL(route.request().url());
    const cardId = url.pathname.split("/api/cards/")[1];

    delete board.cards[cardId];
    board.columns = board.columns.map((column) => ({
      ...column,
      cardIds: column.cardIds.filter((id) => id !== cardId),
    }));

    await fulfill(route, { board });
  });

  await page.route("**/api/cards", async (route) => {
    if (!sessionActive) {
      await fulfill(route, { detail: "Not authenticated." }, 401);
      return;
    }

    const payload = route.request().postDataJSON() as {
      columnId: string;
      title: string;
      details: string;
    };

    createdCardIndex += 1;
    const cardId = `card-playwright-${createdCardIndex}`;

    board.cards[cardId] = {
      id: cardId,
      title: payload.title,
      details: payload.details,
      metadata: {},
    };

    board.columns = board.columns.map((column) =>
      column.id === payload.columnId
        ? { ...column, cardIds: [...column.cardIds, cardId] }
        : column
    );

    await fulfill(route, { board });
  });

  await page.route("**/api/ai/chat", async (route) => {
    if (!sessionActive) {
      await fulfill(route, { detail: "Not authenticated." }, 401);
      return;
    }

    const payload = route.request().postDataJSON() as { prompt: string };
    createdCardIndex += 1;
    const cardId = `card-ai-${createdCardIndex}`;

    board.cards[cardId] = {
      id: cardId,
      title: `AI ${payload.prompt}`,
      details: "Generated by assistant",
      metadata: {},
    };

    board.columns = board.columns.map((column) =>
      column.id === "col-backlog"
        ? { ...column, cardIds: [...column.cardIds, cardId] }
        : column
    );

    await fulfill(route, {
      assistant: { role: "assistant", content: "Added that to backlog." },
      model: "openai/gpt-oss-120b:free",
      parsed: true,
      boardUpdated: true,
      appliedOperations: [{ index: 0, type: "create_card", columnId: "col-backlog" }],
      operationErrors: [],
      board,
    });
  });
};

const login = async (page: Page) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Project Management MVP" })
  ).toBeVisible();
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
};

test("requires login before the kanban board is visible", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Project Management MVP" })
  ).toBeVisible();
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(0);
});

test("adds a card to a column", async ({ page }) => {
  await mockApi(page);
  await login(page);

  const firstColumn = page.locator('[data-testid^="column-"]').first();
  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill("Playwright card");
  await firstColumn.getByPlaceholder("Details").fill("Added via e2e.");
  await firstColumn.getByRole("button", { name: /add card/i }).click();

  await expect(firstColumn.getByText("Playwright card")).toBeVisible();
});

test("moves a card between columns", async ({ page }) => {
  await mockApi(page);
  await login(page);

  const card = page.getByTestId("card-card-1");
  const targetColumn = page.getByTestId("column-col-review");
  const cardBox = await card.boundingBox();
  const columnBox = await targetColumn.boundingBox();
  if (!cardBox || !columnBox) {
    throw new Error("Unable to resolve drag coordinates.");
  }

  await page.mouse.move(cardBox.x + cardBox.width / 2, cardBox.y + cardBox.height / 2);
  await page.mouse.down();
  await page.mouse.move(columnBox.x + columnBox.width / 2, columnBox.y + 120, {
    steps: 12,
  });
  await page.mouse.up();

  await expect(targetColumn.getByTestId("card-card-1")).toBeVisible();
});

test("shows login error for invalid credentials", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("wrong");
  await page.getByRole("button", { name: /sign in/i }).click();

  await expect(
    page.getByText("Invalid credentials. Use user / password.")
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toHaveCount(0);
});

test("logs out and returns to sign-in", async ({ page }) => {
  await mockApi(page);
  await login(page);
  await page.getByRole("button", { name: /log out/i }).click();

  await expect(
    page.getByRole("heading", { name: "Project Management MVP" })
  ).toBeVisible();
});

test("sends AI chat and auto-refreshes board", async ({ page }) => {
  await mockApi(page);
  await login(page);

  await page.getByPlaceholder("Ask AI to update your board...").fill("card from ai");
  await page.getByRole("button", { name: /^send$/i }).click();

  await expect(page.getByText("Added that to backlog.")).toBeVisible();
  await expect(page.getByText("AI card from ai")).toBeVisible();
});
