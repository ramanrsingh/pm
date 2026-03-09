import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthGate } from "@/components/AuthGate";

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

    expect(await screen.findByRole("heading", { name: /project management mvp/i })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /kanban studio/i })).not.toBeInTheDocument();
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

    await screen.findByRole("heading", { name: /project management mvp/i });
    await userEvent.clear(screen.getByLabelText(/password/i));
    await userEvent.type(screen.getByLabelText(/password/i), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid credentials. Use user / password.");
  });

  it("authenticates then logs out", async () => {
    let isLoggedIn = false;
    const boardPayload = {
      board: {
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

        if (url.endsWith("/api/board") && init?.method === "GET") {
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

    await screen.findByRole("heading", { name: /project management mvp/i });
    await userEvent.type(screen.getByLabelText(/password/i), "password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("heading", { name: /kanban studio/i })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /log out/i }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /project management mvp/i })).toBeInTheDocument();
    });
  });
});
