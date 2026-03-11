import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthGate } from "@/components/AuthGate";

const BOARD_ID = "board-1";

describe("AuthGate", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows login form when session check is unauthenticated", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/api/auth/me")) {
          return new Response(JSON.stringify({ detail: "Not authenticated." }), {
            status: 401,
            headers: { "Content-Type": "application/json" },
          });
        }
        throw new Error(`Unexpected request: ${url}`);
      })
    );

    render(<AuthGate />);

    expect(await screen.findByRole("heading", { name: /kanban studio/i })).toBeInTheDocument();
    // Submit button visible in login mode
    expect(screen.getByTestId("auth-submit")).toBeInTheDocument();
  });

  it("shows register mode toggle", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/api/auth/me")) {
          return new Response(JSON.stringify({ detail: "Not authenticated." }), {
            status: 401,
            headers: { "Content-Type": "application/json" },
          });
        }
        throw new Error(`Unexpected request: ${url}`);
      })
    );

    render(<AuthGate />);

    await screen.findByRole("heading", { name: /kanban studio/i });
    const registerButton = screen.getByRole("button", { name: /register/i });
    await userEvent.click(registerButton);

    // Should show confirm password field in register mode
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
  });

  it("shows an error on invalid credentials", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/api/auth/me")) {
          return new Response(JSON.stringify({ detail: "Not authenticated." }), {
            status: 401,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (url.endsWith("/api/auth/login") && init?.method === "POST") {
          return new Response(JSON.stringify({ detail: "Invalid username or password." }), {
            status: 401,
            headers: { "Content-Type": "application/json" },
          });
        }
        throw new Error(`Unexpected request: ${url}`);
      })
    );

    render(<AuthGate />);

    await screen.findByRole("heading", { name: /kanban studio/i });
    await userEvent.clear(screen.getByLabelText(/password/i));
    await userEvent.type(screen.getByLabelText(/password/i), "wrong");
    await userEvent.click(screen.getByTestId("auth-submit"));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid username or password.");
  });

  it("authenticates then logs out", async () => {
    let isLoggedIn = false;
    const boardListPayload = {
      boards: [{ id: BOARD_ID, name: "Project Board", createdAt: "2024-01-01T00:00:00" }],
    };
    const boardPayload = {
      board: {
        id: BOARD_ID,
        name: "Project Board",
        columns: [
          { id: "col-backlog", title: "Backlog", cardIds: ["card-1"] },
          { id: "col-discovery", title: "Discovery", cardIds: [] },
          { id: "col-progress", title: "In Progress", cardIds: [] },
          { id: "col-review", title: "Review", cardIds: [] },
          { id: "col-done", title: "Done", cardIds: [] },
        ],
        cards: {
          "card-1": {
            id: "card-1",
            title: "Seed",
            details: "Seed details",
            metadata: {},
          },
        },
      },
    };

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);

        if (url.endsWith("/api/auth/me")) {
          if (isLoggedIn) {
            return new Response(JSON.stringify({ status: "authenticated", username: "user" }), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            });
          }
          return new Response(JSON.stringify({ detail: "Not authenticated." }), {
            status: 401,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url.endsWith("/api/auth/login") && init?.method === "POST") {
          isLoggedIn = true;
          return new Response(JSON.stringify({ status: "ok" }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url.endsWith("/api/boards") && (!init?.method || init.method === "GET")) {
          return new Response(JSON.stringify(boardListPayload), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url.endsWith(`/api/boards/${BOARD_ID}`) && (!init?.method || init.method === "GET")) {
          return new Response(JSON.stringify(boardPayload), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url.endsWith("/api/auth/logout") && init?.method === "POST") {
          isLoggedIn = false;
          return new Response(JSON.stringify({ status: "ok" }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        throw new Error(`Unexpected request: ${url}`);
      })
    );

    render(<AuthGate />);

    await screen.findByRole("heading", { name: /kanban studio/i });
    await userEvent.type(screen.getByLabelText(/password/i), "password");
    await userEvent.click(screen.getByTestId("auth-submit"));

    // Should render the board after login
    expect(await screen.findByTestId("column-col-backlog")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /log out/i }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /kanban studio/i })).toBeInTheDocument();
    });
  });
});
