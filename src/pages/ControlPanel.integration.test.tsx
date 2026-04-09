import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";

import ControlPanel from "@/pages/ControlPanel";
import * as Api from "@/Api";
import { useAuth } from "@/auth/AuthProvider";

vi.mock("@/Api", async () => {
  const actual = await vi.importActual<typeof import("@/Api")>("@/Api");
  return {
    ...actual,
    listPortfolios: vi.fn(),
    listUsers: vi.fn(),
    updateUserRole: vi.fn(),
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

function renderControlPanel() {
  return render(
    <MemoryRouter initialEntries={["/control-panel"]}>
      <Routes>
        <Route path="/dashboard" element={<div>Dashboard</div>} />
        <Route path="/control-panel" element={<ControlPanel />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ControlPanel", () => {
  beforeEach(() => {
    mockedApi.listPortfolios.mockResolvedValue({
      items: [
        {
          id: "p1",
          name: "Alpha",
          emoji: "A",
          balance_usd: "100.00",
          pnl_day_usd: "0.00",
          kind: "personal",
          visibility: "public",
          owner_id: "u1",
          owner_email: "owner@example.com",
        },
      ],
      page: 1,
      page_size: 50,
      total_items: 1,
      total_pages: 1,
    });
    mockedApi.isAuthError.mockReturnValue(false);
  });

  it("shows read-only portfolio moderation view for managers", async () => {
    mockedUseAuth.mockReturnValue({
      user: { id: "m1", email: "manager@example.com", role: "manager" },
      isAuthenticated: true,
      isLoading: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
      refreshUser: vi.fn(),
    });

    renderControlPanel();

    expect(await screen.findByText("All portfolios")).toBeInTheDocument();
    expect(screen.queryByText("Users and roles")).not.toBeInTheDocument();
    expect(screen.getByText("Read-only access to all portfolios.")).toBeInTheDocument();
  });

  it("allows admins to change user roles", async () => {
    const refreshUser = vi.fn().mockResolvedValue(undefined);
    mockedUseAuth.mockReturnValue({
      user: { id: "a1", email: "admin@example.com", role: "admin" },
      isAuthenticated: true,
      isLoading: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
      refreshUser,
    });
    mockedApi.listUsers.mockResolvedValue([
      { id: "a1", email: "admin@example.com", role: "admin", created_at: "2026-04-09T12:00:00Z" },
      { id: "u1", email: "user@example.com", role: "user", created_at: "2026-04-09T12:00:00Z" },
    ]);
    mockedApi.updateUserRole.mockResolvedValue({
      id: "u1",
      email: "user@example.com",
      role: "manager",
    });

    renderControlPanel();

    expect(await screen.findByText("Users and roles")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getAllByRole("combobox")[1], "manager");

    await waitFor(() =>
      expect(mockedApi.updateUserRole).toHaveBeenCalledWith("u1", { role: "manager" }),
    );
    expect(refreshUser).not.toHaveBeenCalled();
  });
});
