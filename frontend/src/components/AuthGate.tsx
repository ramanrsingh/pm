"use client";

import { FormEvent, useEffect, useState } from "react";
import { KanbanBoard } from "@/components/KanbanBoard";

type AuthState = "checking" | "authenticated" | "unauthenticated";
type FormMode = "login" | "register";

export const AuthGate = () => {
  const [authState, setAuthState] = useState<AuthState>("checking");
  const [formMode, setFormMode] = useState<FormMode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const checkSession = async () => {
    const response = await fetch("/api/auth/me", {
      method: "GET",
      credentials: "include",
    });
    if (response.ok) {
      setAuthState("authenticated");
      setError(null);
      return;
    }
    setAuthState("unauthenticated");
  };

  useEffect(() => {
    void checkSession();
  }, []);

  const switchMode = (mode: FormMode) => {
    setFormMode(mode);
    setError(null);
    setPassword("");
    setConfirmPassword("");
  };

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        setError("Invalid username or password.");
        return;
      }

      setAuthState("authenticated");
      setPassword("");
    } catch {
      setError("Unable to sign in right now. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRegister = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const response = await fetch("/api/auth/register", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string };
        setError(payload.detail ?? "Registration failed. Please try again.");
        return;
      }

      setAuthState("authenticated");
      setPassword("");
      setConfirmPassword("");
    } catch {
      setError("Unable to register right now. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLogout = async () => {
    await fetch("/api/auth/logout", {
      method: "POST",
      credentials: "include",
    });
    setAuthState("unauthenticated");
    setUsername("");
    setPassword("");
    setConfirmPassword("");
  };

  if (authState === "checking") {
    return (
      <main className="grid min-h-screen place-items-center px-6">
        <div className="flex flex-col items-center gap-4">
          <div className="animate-spin-smooth h-7 w-7 rounded-full border-2 border-[var(--stroke)] border-t-[var(--primary-blue)]" />
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
            Checking session
          </p>
        </div>
      </main>
    );
  }

  if (authState === "authenticated") {
    return <KanbanBoard onLogout={handleLogout} />;
  }

  return (
    <div className="relative overflow-hidden">
      {/* Background decorative gradients */}
      <div className="pointer-events-none absolute left-0 top-0 h-[600px] w-[600px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.2)_0%,_rgba(32,157,215,0.04)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[500px] w-[500px] translate-x-1/3 translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.15)_0%,_rgba(117,57,145,0.04)_55%,_transparent_75%)]" />

      <main className="relative grid min-h-screen place-items-center px-6">
        <section className="animate-slide-up w-full max-w-sm">
          {/* Logo */}
          <div className="mb-8 flex flex-col items-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-3xl bg-[var(--navy-dark)] shadow-[0_8px_24px_rgba(3,33,71,0.2)]">
              <svg width="28" height="28" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <rect x="2" y="2" width="7" height="10" rx="1.5" fill="white" opacity="0.9" />
                <rect x="11" y="2" width="7" height="6" rx="1.5" fill="white" opacity="0.5" />
                <rect x="11" y="10" width="7" height="8" rx="1.5" fill="white" opacity="0.7" />
                <rect x="2" y="14" width="7" height="4" rx="1.5" fill="white" opacity="0.5" />
              </svg>
            </div>
            <div className="text-center">
              <p className="text-[10px] font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                Project Management
              </p>
              <h1 className="mt-1.5 font-display text-2xl font-semibold text-[var(--navy-dark)]">
                Kanban Studio
              </h1>
            </div>
          </div>

          {/* Card */}
          <div className="rounded-3xl border border-[var(--stroke)] bg-white/90 p-7 shadow-[var(--shadow-lg)] backdrop-blur">
            {/* Mode tabs */}
            <div className="mb-5 flex rounded-xl border border-[var(--stroke)] bg-[var(--surface)] p-1">
              <button
                type="button"
                onClick={() => switchMode("login")}
                className={`flex-1 rounded-lg py-2 text-xs font-semibold uppercase tracking-[0.15em] transition-all duration-150 ${
                  formMode === "login"
                    ? "bg-white text-[var(--navy-dark)] shadow-sm"
                    : "text-[var(--gray-text)] hover:text-[var(--navy-dark)]"
                }`}
              >
                Sign in
              </button>
              <button
                type="button"
                onClick={() => switchMode("register")}
                className={`flex-1 rounded-lg py-2 text-xs font-semibold uppercase tracking-[0.15em] transition-all duration-150 ${
                  formMode === "register"
                    ? "bg-white text-[var(--navy-dark)] shadow-sm"
                    : "text-[var(--gray-text)] hover:text-[var(--navy-dark)]"
                }`}
              >
                Register
              </button>
            </div>

            <form
              className="space-y-4"
              onSubmit={formMode === "login" ? handleLogin : handleRegister}
            >
              <div>
                <label
                  htmlFor="login-username"
                  className="block text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]"
                >
                  Username
                </label>
                <input
                  id="login-username"
                  className="mt-2 w-full rounded-xl border border-[var(--stroke)] bg-[var(--surface)] px-3.5 py-2.5 text-sm font-medium text-[var(--navy-dark)] outline-none transition-colors duration-150 focus:border-[var(--primary-blue)] focus:bg-white"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  autoComplete="username"
                />
              </div>

              <div>
                <label
                  htmlFor="login-password"
                  className="block text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]"
                >
                  Password
                </label>
                <input
                  id="login-password"
                  type="password"
                  className="mt-2 w-full rounded-xl border border-[var(--stroke)] bg-[var(--surface)] px-3.5 py-2.5 text-sm font-medium text-[var(--navy-dark)] outline-none transition-colors duration-150 focus:border-[var(--primary-blue)] focus:bg-white"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete={formMode === "login" ? "current-password" : "new-password"}
                />
              </div>

              {formMode === "register" && (
                <div>
                  <label
                    htmlFor="confirm-password"
                    className="block text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]"
                  >
                    Confirm password
                  </label>
                  <input
                    id="confirm-password"
                    type="password"
                    className="mt-2 w-full rounded-xl border border-[var(--stroke)] bg-[var(--surface)] px-3.5 py-2.5 text-sm font-medium text-[var(--navy-dark)] outline-none transition-colors duration-150 focus:border-[var(--primary-blue)] focus:bg-white"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    autoComplete="new-password"
                  />
                </div>
              )}

              {error && (
                <div className="flex items-center gap-2 rounded-xl border border-red-100 bg-red-50 px-3.5 py-2.5">
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                    <circle cx="6" cy="6" r="5" stroke="#f87171" strokeWidth="1.2" />
                    <path d="M6 3.5v3M6 8v.5" stroke="#f87171" strokeWidth="1.2" strokeLinecap="round" />
                  </svg>
                  <p role="alert" className="text-xs font-medium text-red-500">
                    {error}
                  </p>
                </div>
              )}

              <button
                type="submit"
                data-testid="auth-submit"
                disabled={isSubmitting}
                className="mt-1 w-full rounded-full bg-[var(--navy-dark)] px-4 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-white transition-all duration-150 hover:bg-[var(--primary-blue)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSubmitting
                  ? formMode === "login" ? "Signing in..." : "Creating account..."
                  : formMode === "login" ? "Sign in" : "Create account"}
              </button>
            </form>

            {formMode === "login" && (
              <p className="mt-4 text-center text-[10px] text-[var(--gray-text)]">
                Default credentials: <strong className="text-[var(--navy-dark)]">user</strong> /{" "}
                <strong className="text-[var(--navy-dark)]">password</strong>
              </p>
            )}
          </div>
        </section>
      </main>
    </div>
  );
};
