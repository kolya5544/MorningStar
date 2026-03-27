import {
  deletePortfolio,
  isAuthError,
  listPortfolios,
  listUsers,
  updateUserRole,
  type PortfolioSummary,
  type Role,
  type UserListItem,
} from "@/Api";
import { useAuth } from "@/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import { useSeo } from "@/lib/seo";
import { Home, LogOut, RefreshCw, Shield, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

function fmtMoney(value: string) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(Number(value || "0"));
}

export default function ControlPanel() {
  useSeo({
    title: "Control Panel | MorningStar",
    description: "Restricted administration area for MorningStar roles and portfolio moderation.",
    canonicalPath: "/control-panel",
    robots: "noindex,nofollow",
  });

  const nav = useNavigate();
  const { user, signOut, refreshUser } = useAuth();
  const [portfolios, setPortfolios] = useState<PortfolioSummary[]>([]);
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyDeleteId, setBusyDeleteId] = useState<string | null>(null);
  const [busyRoleId, setBusyRoleId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const portfolioData = await listPortfolios({ page: 1, page_size: 50, sort_by: "created_at", sort_dir: "desc" });
      setPortfolios(portfolioData.items);

      if (user?.role === "admin") {
        const userData = await listUsers();
        setUsers(userData);
      } else {
        setUsers([]);
      }
    } catch (err: unknown) {
      if (isAuthError(err)) {
        await signOut();
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load control panel");
    } finally {
      setLoading(false);
    }
  }, [signOut, user?.role]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleDeletePortfolio = async (portfolioId: string) => {
    if (user?.role !== "admin") return;
    if (!confirm("Delete this portfolio?")) return;

    try {
      setBusyDeleteId(portfolioId);
      await deletePortfolio(portfolioId);
      setPortfolios((prev) => prev.filter((portfolio) => portfolio.id !== portfolioId));
    } catch (err: unknown) {
      if (isAuthError(err)) {
        await signOut();
        return;
      }
      alert(err instanceof Error ? err.message : "Failed to delete portfolio");
    } finally {
      setBusyDeleteId(null);
    }
  };

  const handleChangeRole = async (userId: string, nextRole: Role) => {
    try {
      setBusyRoleId(userId);
      const updated = await updateUserRole(userId, { role: nextRole });
      setUsers((prev) => prev.map((item) => (item.id === userId ? { ...item, role: updated.role } : item)));
      if (userId === user?.id) {
        await refreshUser();
      }
    } catch (err: unknown) {
      if (isAuthError(err)) {
        await signOut();
        return;
      }
      alert(err instanceof Error ? err.message : "Failed to update role");
    } finally {
      setBusyRoleId(null);
    }
  };

  return (
    <div className="min-h-screen bg-black text-white">
      <header className="sticky top-0 z-20 w-full backdrop-blur bg-black/30">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center gap-3">
              <Shield className="h-6 w-6 text-zinc-200" />
              <div>
                <div className="text-lg font-semibold tracking-wide">Control Panel</div>
                <div className="text-xs text-zinc-400">
                  {user?.role === "admin" ? "Admin" : "Manager"} mode
                </div>
              </div>
            </div>
            <nav className="flex items-center gap-2">
              <Button variant="outline" onClick={() => nav("/dashboard")}>
                <Home className="mr-2 h-4 w-4" /> Dashboard
              </Button>
              <Button variant="outline" onClick={() => void load()} disabled={loading}>
                <RefreshCw className="mr-2 h-4 w-4" /> Refresh
              </Button>
              <Button variant="outline" onClick={() => void signOut()}>
                <LogOut className="mr-2 h-4 w-4" /> Logout
              </Button>
            </nav>
          </div>
        </div>
        <div className="h-px w-full bg-gradient-to-r from-transparent via-[#16335f] to-transparent opacity-50" />
      </header>

      <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8 space-y-10">
        {loading && <div className="text-zinc-400">Loading control panel...</div>}
        {!loading && error && <div className="text-sm text-red-400">{error}</div>}

        {!loading && !error && (
          <>
            <section className="space-y-4">
              <div className="flex items-end justify-between gap-4">
                <div>
                  <h1 className="text-2xl font-semibold">All portfolios</h1>
                  <p className="text-sm text-zinc-400">
                    {user?.role === "admin"
                      ? "Full access to all portfolios."
                      : "Read-only access to all portfolios."}
                  </p>
                </div>
              </div>

              <div className="overflow-hidden rounded-2xl border border-white/10 bg-zinc-950/70">
                <div className="grid grid-cols-[1.3fr_1fr_110px_130px_170px] gap-3 border-b border-white/10 px-4 py-3 text-xs uppercase tracking-wide text-zinc-400">
                  <div>Name</div>
                  <div>Owner</div>
                  <div>Kind</div>
                  <div>Balance</div>
                  <div className="text-right">Actions</div>
                </div>
                {portfolios.length === 0 ? (
                  <div className="px-4 py-6 text-sm text-zinc-400">No portfolios found.</div>
                ) : (
                  portfolios.map((portfolio) => (
                    <div
                      key={portfolio.id}
                      className="grid grid-cols-[1.3fr_1fr_110px_130px_170px] gap-3 border-b border-white/5 px-4 py-4 last:border-b-0"
                    >
                      <div>
                        <div className="font-medium">
                          {portfolio.emoji ?? "[P]"} {portfolio.name}
                        </div>
                        <div className="text-xs text-zinc-500">{portfolio.id}</div>
                      </div>
                      <div className="text-sm text-zinc-300">
                        {portfolio.owner_email ?? portfolio.owner_id ?? "Unknown"}
                      </div>
                      <div className="text-sm text-zinc-300">
                        {portfolio.kind}
                        {portfolio.visibility ? ` / ${portfolio.visibility}` : ""}
                      </div>
                      <div className="text-sm text-zinc-300">{fmtMoney(portfolio.balance_usd)}</div>
                      <div className="flex justify-end gap-2">
                        <Button variant="outline" size="sm" onClick={() => nav(`/dashboard/${portfolio.id}`)}>
                          Open
                        </Button>
                        {user?.role === "admin" && (
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={busyDeleteId === portfolio.id}
                            onClick={() => void handleDeletePortfolio(portfolio.id)}
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            Delete
                          </Button>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </section>

            {user?.role === "admin" && (
              <section className="space-y-4">
                <div>
                  <h2 className="text-2xl font-semibold">Users and roles</h2>
                  <p className="text-sm text-zinc-400">Administrators can manage user roles here.</p>
                </div>

                <div className="overflow-hidden rounded-2xl border border-white/10 bg-zinc-950/70">
                  <div className="grid grid-cols-[1.2fr_140px_220px] gap-3 border-b border-white/10 px-4 py-3 text-xs uppercase tracking-wide text-zinc-400">
                    <div>Email</div>
                    <div>Role</div>
                    <div className="text-right">Change role</div>
                  </div>
                  {users.map((item) => (
                    <div
                      key={item.id}
                      className="grid grid-cols-[1.2fr_140px_220px] gap-3 border-b border-white/5 px-4 py-4 last:border-b-0"
                    >
                      <div>
                        <div className="font-medium">{item.email}</div>
                        <div className="text-xs text-zinc-500">{item.id}</div>
                      </div>
                      <div className="text-sm text-zinc-300">{item.role}</div>
                      <div className="flex justify-end">
                        <select
                          className="rounded-md border border-white/10 bg-black px-3 py-2 text-sm text-white outline-none"
                          value={item.role}
                          disabled={busyRoleId === item.id}
                          onChange={(e) => void handleChangeRole(item.id, e.target.value as Role)}
                        >
                          <option value="user">user</option>
                          <option value="manager">manager</option>
                          <option value="admin">admin</option>
                        </select>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}
