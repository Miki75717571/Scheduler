import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../i18n";
import { AuthProvider } from "../lib/auth-context";
import { LoginPage } from "./LoginPage";

function renderLoginPage() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("LoginPage", () => {
  beforeEach(() => {
    void i18n.changeLanguage("en");
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/auth/refresh")) {
          return Promise.resolve(
            new Response(JSON.stringify({ detail: { message_key: "auth.missing_token" } }), {
              status: 401,
            }),
          );
        }
        if (url.endsWith("/auth/login")) {
          return Promise.resolve(
            new Response(JSON.stringify({ detail: { message_key: "auth.invalid_credentials" } }), {
              status: 401,
            }),
          );
        }
        return Promise.resolve(new Response("{}", { status: 200 }));
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows a translated error on invalid credentials", async () => {
    renderLoginPage();
    const user = userEvent.setup();

    await waitFor(() => screen.getByLabelText(/email/i));

    await user.type(screen.getByLabelText(/email/i), "wrong@example.com");
    await user.type(screen.getByLabelText(/password/i), "wrongpassword");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/incorrect email or password/i)).toBeInTheDocument();
  });
});
