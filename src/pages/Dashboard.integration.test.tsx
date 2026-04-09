import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";

import Dashboard from "@/pages/Dashboard";
import * as Api from "@/Api";
import { useAuth } from "@/auth/AuthProvider";

vi.mock("@/Api", async () => {
  const actual = await vi.importActual<typeof import("@/Api")>("@/Api");
  return {
    ...actual,
    listPortfolios: vi.fn(),
    createPortfolio: vi.fn(),
    importPortfolio: vi.fn(),
    deletePortfolio: vi.fn(),
    isAuthError: vi.fn(),
  };
});

vi.mock("@/auth/AuthProvider", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/lib/seo", () => ({
  useSeo: vi.fn(),
}));

const mockedApi = vi.mocked(Api);
const mockedUseAuth = vi.mocked(useAuth);

function renderDashboard(initialEntry = "/dashboard") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/dashboard/:id" element={<div>Portfolio page</div>} />
        <Route path="/control-panel" element={<div>Control panel</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Dashboard", () => {
  beforeEach(() => {
    mockedUseAuth.mockReturnValue({
      user: { id: "u1", email: "user@example.com", role: "user" },
      isAuthenticated: true,
      isLoading: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
      refreshUser: vi.fn(),
    });
    mockedApi.isAuthError.mockReturnValue(false);
    mockedApi.listPortfolios.mockResolvedValue({
      items: [
        {
          id: "p1",
          name: "Alpha",
          emoji: "A",
          balance_usd: "100.00",
          pnl_day_usd: "10.00",
          kind: "personal",
          visibility: "public",
          owner_id: "u1",
          owner_email: "user@example.com",
        },
      ],
      page: 2,
      page_size: 6,
      total_items: 7,
      total_pages: 3,
    });
    mockedApi.createPortfolio.mockResolvedValue({
      id: "p2",
      name: "Created",
      emoji: "C",
      balance_usd: "0.00",
      pnl_day_usd: "0.00",
      kind: "personal",
      visibility: "private",
      owner_id: "u1",
      owner_email: "user@example.com",
      created_at: "2026-04-09T10:00:00Z",
    });
    mockedApi.importPortfolio.mockResolvedValue({
      id: "p3",
      name: "Imported",
      emoji: "I",
      balance_usd: "0.00",
      pnl_day_usd: "0.00",
      kind: "subscribed",
      visibility: "private",
      owner_id: "u1",
      owner_email: "user@example.com",
      created_at: "2026-04-09T10:00:00Z",
    });
  });

  it("loads portfolios from URL filters and supports pagination navigation", async () => {
    renderDashboard("/dashboard?search=btc&page=2&sort_by=name&sort_dir=asc");

    await waitFor(() =>
      expect(mockedApi.listPortfolios).toHaveBeenCalledWith({
        search: "btc",
        kind: "",
        visibility: "",
        sort_by: "name",
        sort_dir: "asc",
        page: 2,
        page_size: 6,
      }),
    );
    expect(await screen.findByText("Alpha")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() =>
      expect(mockedApi.listPortfolios).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 3 }),
      ),
    );
  });

  it("creates a portfolio through the modal form", async () => {
    renderDashboard();

    await screen.findByText("Alpha");
    await userEvent.click(screen.getByRole("button", { name: /new portfolio/i }));
    await userEvent.type(screen.getByPlaceholderText("My portfolio"), "Created");
    await userEvent.click(screen.getAllByRole("button", { name: /^Create$/ }).at(-1)!);

    await waitFor(() =>
      expect(mockedApi.createPortfolio).toHaveBeenCalledWith({
        name: "Created",
        emoji: undefined,
        visibility: "private",
      }),
    );
    expect(await screen.findByText("Created")).toBeInTheDocument();
  });

  it("signs the user out on auth errors from the backend", async () => {
    const signOut = vi.fn().mockResolvedValue(undefined);
    mockedUseAuth.mockReturnValue({
      user: { id: "u1", email: "user@example.com", role: "user" },
      isAuthenticated: true,
      isLoading: false,
      signIn: vi.fn(),
      signOut,
      refreshUser: vi.fn(),
    });
    mockedApi.listPortfolios.mockRejectedValue(new Error("401 Unauthorized"));
    mockedApi.isAuthError.mockReturnValue(true);

    renderDashboard();

    await waitFor(() => expect(signOut).toHaveBeenCalled());
  });
});
