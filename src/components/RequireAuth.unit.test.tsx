import React from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";

import { RequireAuth } from "@/components/RequireAuth";
import { useAuth } from "@/auth/AuthProvider";

vi.mock("@/auth/AuthProvider", () => ({
  useAuth: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);

describe("RequireAuth", () => {
  it("shows a session check state while auth is loading", () => {
    mockedUseAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: true,
      signIn: vi.fn(),
      signOut: vi.fn(),
      refreshUser: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <RequireAuth>
          <div>Protected</div>
        </RequireAuth>
      </MemoryRouter>,
    );

    expect(screen.getByText("Checking session...")).toBeInTheDocument();
  });

  it("redirects unauthenticated users to landing page", () => {
    mockedUseAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
      refreshUser: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/" element={<div>Landing</div>} />
          <Route
            path="/dashboard"
            element={
              <RequireAuth>
                <div>Protected</div>
              </RequireAuth>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Landing")).toBeInTheDocument();
  });

  it("redirects users without the required role back to dashboard", () => {
    mockedUseAuth.mockReturnValue({
      user: { id: "u1", email: "user@example.com", role: "user" },
      isAuthenticated: true,
      isLoading: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
      refreshUser: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={["/control-panel"]}>
        <Routes>
          <Route path="/dashboard" element={<div>Dashboard</div>} />
          <Route
            path="/control-panel"
            element={
              <RequireAuth allowedRoles={["manager", "admin"]}>
                <div>Admin area</div>
              </RequireAuth>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });
});
