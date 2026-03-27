import {
  createPortfolio,
  deletePortfolio,
  importPortfolio,
  isAuthError,
  listPortfolios,
  type PortfolioKind,
  type PortfolioDetail as ServerPortfolioDetail,
  type PortfolioSummary as ServerPortfolioSummary,
  type Visibility,
} from "@/Api";
import { useAuth } from "@/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Input } from "@/components/ui/input";
import { useSeo } from "@/lib/seo";
import { Home, LogOut, Plus, Search, Shield, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

export type Portfolio = {
  id: string;
  name: string;
  emoji: string;
  balance: number;
  pnlDay: number;
  kind: "personal" | "subscribed";
  visibility?: "public" | "private";
  ownerId?: string | null;
};

type DashboardFilters = {
  search: string;
  kind: PortfolioKind | "";
  visibility: Visibility | "";
  sort_by: "created_at" | "name" | "balance_usd";
  sort_dir: "asc" | "desc";
  page: number;
  page_size: number;
};

function fmtMoney(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function mapSummary(portfolio: ServerPortfolioSummary): Portfolio {
  return {
    id: portfolio.id,
    name: portfolio.name,
    emoji: portfolio.emoji ?? "[P]",
    balance: Number(portfolio.balance_usd ?? "0"),
    pnlDay: Number(portfolio.pnl_day_usd ?? "0"),
    kind: portfolio.kind,
    visibility: portfolio.visibility ?? undefined,
    ownerId: portfolio.owner_id ?? null,
  };
}

export default function Dashboard() {
  const nav = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user, signOut } = useAuth();
  const [items, setItems] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [openAdd, setOpenAdd] = useState(false);
  const [meta, setMeta] = useState({ page: 1, totalPages: 1, totalItems: 0 });

  const filters = useMemo<DashboardFilters>(() => ({
    search: searchParams.get("search") ?? "",
    kind: (searchParams.get("kind") as PortfolioKind | null) ?? "",
    visibility: (searchParams.get("visibility") as Visibility | null) ?? "",
    sort_by: (searchParams.get("sort_by") as "created_at" | "name" | "balance_usd" | null) ?? "created_at",
    sort_dir: (searchParams.get("sort_dir") as "asc" | "desc" | null) ?? "desc",
    page: Number(searchParams.get("page") ?? "1") || 1,
    page_size: Number(searchParams.get("page_size") ?? "6") || 6,
  }), [searchParams]);

  useSeo({
    title: "Dashboard | MorningStar",
    description: "Private MorningStar dashboard for managing crypto portfolios and filters.",
    canonicalPath: "/dashboard",
    robots: "noindex,nofollow",
  });

  const loadPortfolios = useCallback(async () => {
    try {
      setLoading(true);
      setErr(null);
      const data = await listPortfolios(filters);
      setItems(data.items.map(mapSummary));
      setMeta({ page: data.page, totalPages: data.total_pages, totalItems: data.total_items });
    } catch (error: unknown) {
      if (isAuthError(error)) {
        await signOut();
        return;
      }
      setErr(error instanceof Error ? error.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [filters, signOut]);

  useEffect(() => {
    void loadPortfolios();
  }, [loadPortfolios]);

  return (
    <div className="min-h-screen bg-black text-white">
      <header className="sticky top-0 z-20 w-full backdrop-blur bg-black/30">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center gap-3">
              <img
                src="/morningstar.svg"
                alt="MorningStar"
                width={32}
                height={32}
                className="h-8 w-8 shrink-0 align-middle"
              />
              <span className="text-lg font-semibold tracking-wide">MorningStar</span>
              {user?.role && user.role !== "user" && (
                <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-xs uppercase tracking-wide text-zinc-300">
                  {user.role}
                </span>
              )}
            </div>
            <nav className="flex items-center gap-2">
              <Button variant="outline" onClick={() => nav("/dashboard")}>
                <Home className="mr-2 h-4 w-4" /> Home
              </Button>
              {(user?.role === "manager" || user?.role === "admin") && (
                <Button variant="outline" onClick={() => nav("/control-panel")}>
                  <Shield className="mr-2 h-4 w-4" /> Control Panel
                </Button>
              )}
              <Button variant="outline" onClick={() => void signOut()}>
                <LogOut className="mr-2 h-4 w-4" /> Logout
              </Button>
            </nav>
          </div>
        </div>
        <div className="h-px w-full bg-gradient-to-r from-transparent via-[#16335f] to-transparent opacity-50" />
      </header>

      <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-semibold">
            {user?.role === "manager" ? "Available portfolios" : "Your portfolios"}
          </h1>
          {user && (
            <Button onClick={() => setOpenAdd(true)}>
              <Plus className="mr-2 h-4 w-4" /> New portfolio
            </Button>
          )}
        </div>

        <section className="mb-6 rounded-2xl border border-white/10 bg-zinc-950/70 p-4">
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1.6fr_repeat(4,0.8fr)]">
            <label className="block">
              <div className="mb-1 text-xs uppercase tracking-wide text-zinc-500">Search</div>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
                <Input
                  className="pl-9"
                  value={filters.search}
                  onChange={(e) => {
                    const next = new URLSearchParams(searchParams);
                    if (e.target.value) next.set("search", e.target.value);
                    else next.delete("search");
                    next.set("page", "1");
                    setSearchParams(next);
                  }}
                  placeholder="Portfolio name or owner"
                />
              </div>
            </label>
            <label className="block">
              <div className="mb-1 text-xs uppercase tracking-wide text-zinc-500">Kind</div>
              <select
                className="h-10 w-full rounded-md border border-white/10 bg-black px-3 text-sm text-white outline-none"
                value={filters.kind}
                onChange={(e) => {
                  const next = new URLSearchParams(searchParams);
                  if (e.target.value) next.set("kind", e.target.value);
                  else next.delete("kind");
                  next.set("page", "1");
                  setSearchParams(next);
                }}
              >
                <option value="">all</option>
                <option value="personal">personal</option>
                <option value="subscribed">subscribed</option>
              </select>
            </label>
            <label className="block">
              <div className="mb-1 text-xs uppercase tracking-wide text-zinc-500">Visibility</div>
              <select
                className="h-10 w-full rounded-md border border-white/10 bg-black px-3 text-sm text-white outline-none"
                value={filters.visibility}
                onChange={(e) => {
                  const next = new URLSearchParams(searchParams);
                  if (e.target.value) next.set("visibility", e.target.value);
                  else next.delete("visibility");
                  next.set("page", "1");
                  setSearchParams(next);
                }}
              >
                <option value="">all</option>
                <option value="private">private</option>
                <option value="public">public</option>
              </select>
            </label>
            <label className="block">
              <div className="mb-1 text-xs uppercase tracking-wide text-zinc-500">Sort By</div>
              <select
                className="h-10 w-full rounded-md border border-white/10 bg-black px-3 text-sm text-white outline-none"
                value={filters.sort_by}
                onChange={(e) => {
                  const next = new URLSearchParams(searchParams);
                  next.set("sort_by", e.target.value);
                  setSearchParams(next);
                }}
              >
                <option value="created_at">created</option>
                <option value="name">name</option>
                <option value="balance_usd">balance</option>
              </select>
            </label>
            <label className="block">
              <div className="mb-1 text-xs uppercase tracking-wide text-zinc-500">Direction</div>
              <select
                className="h-10 w-full rounded-md border border-white/10 bg-black px-3 text-sm text-white outline-none"
                value={filters.sort_dir}
                onChange={(e) => {
                  const next = new URLSearchParams(searchParams);
                  next.set("sort_dir", e.target.value);
                  setSearchParams(next);
                }}
              >
                <option value="desc">desc</option>
                <option value="asc">asc</option>
              </select>
            </label>
          </div>
        </section>

        {loading && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <div
                key={index}
                className="h-[140px] rounded-2xl border border-white/10 bg-zinc-950/80 p-4 animate-pulse"
              />
            ))}
          </div>
        )}

        {!loading && err && (
          <div className="text-sm text-red-400">
            {err}{" "}
            <button className="underline decoration-dotted" onClick={() => void loadPortfolios()}>
              retry
            </button>
          </div>
        )}

        {!loading && !err && items.length === 0 && (
          <div className="text-zinc-400">
            {user?.role === "manager" ? "No portfolios available." : "No portfolios yet. Create the first one."}
          </div>
        )}

        {!loading && !err && items.length > 0 && (
          <div className="grid grid-cols-1 gap-4 place-items-stretch sm:grid-cols-2 lg:grid-cols-3">
            {items.map((portfolio) => (
              <button
                key={portfolio.id}
                onClick={() => nav(`/dashboard/${portfolio.id}`)}
                className="group flex flex-col rounded-2xl border border-white/10 bg-zinc-950/80 p-4 text-left transition hover:bg-white/5"
              >
                <div className="flex items-start justify-between">
                  <div className="text-2xl leading-none" aria-hidden>
                    {portfolio.emoji}
                  </div>
                  <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-xs text-zinc-300">
                    {portfolio.kind}
                    {portfolio.kind === "personal" && portfolio.visibility ? ` - ${portfolio.visibility}` : ""}
                  </span>
                </div>
                <div className="mt-3 line-clamp-1 text-base font-medium">{portfolio.name}</div>
                <div className="mt-1 text-sm text-zinc-400">{fmtMoney(portfolio.balance)}</div>
                <div
                  className={`mt-4 text-sm font-medium ${
                    portfolio.pnlDay >= 0 ? "text-emerald-400" : "text-red-400"
                  }`}
                >
                  {portfolio.pnlDay >= 0 ? "+" : ""}
                  {fmtMoney(portfolio.pnlDay)} today
                </div>
                {(user?.role === "admin" || portfolio.ownerId === user?.id) && (
                  <div className="mt-4 flex justify-end">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={async (event) => {
                        event.stopPropagation();
                        if (!confirm("Delete this portfolio?")) return;
                        try {
                          await deletePortfolio(portfolio.id);
                          void loadPortfolios();
                        } catch (error: unknown) {
                          alert(error instanceof Error ? error.message : "Failed to delete portfolio");
                        }
                      }}
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Delete
                    </Button>
                  </div>
                )}
              </button>
            ))}
          </div>
        )}

        {!loading && !err && (
          <div className="mt-6 flex items-center justify-between text-sm text-zinc-400">
            <div>
              {meta.totalItems} item(s), page {meta.page} of {meta.totalPages}
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={meta.page <= 1}
                onClick={() => {
                  const next = new URLSearchParams(searchParams);
                  next.set("page", String(Math.max(1, filters.page - 1)));
                  setSearchParams(next);
                }}
              >
                Prev
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={meta.page >= meta.totalPages}
                onClick={() => {
                  const next = new URLSearchParams(searchParams);
                  next.set("page", String(Math.min(meta.totalPages, filters.page + 1)));
                  setSearchParams(next);
                }}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </main>

      <AddPortfolioModal
        open={openAdd}
        onClose={() => setOpenAdd(false)}
        onCreate={async (data) => {
          const created: ServerPortfolioDetail = await createPortfolio({
            name: data.name,
            emoji: data.emoji,
            visibility: data.visibility as Visibility,
          });
          setItems((prev) => [mapSummary(created), ...prev]);
          setOpenAdd(false);
        }}
        onSubscribe={async (portfolioId) => {
          const created = await importPortfolio(portfolioId);
          setItems((prev) => [mapSummary(created), ...prev]);
          setOpenAdd(false);
        }}
      />
    </div>
  );
}

type CreatePayload = {
  name: string;
  emoji?: string;
  visibility: "public" | "private";
};

function AddPortfolioModal({
  open,
  onClose,
  onCreate,
  onSubscribe,
}: {
  open: boolean;
  onClose: () => void;
  onCreate: (data: CreatePayload) => void | Promise<void>;
  onSubscribe: (portfolioId: string) => void | Promise<void>;
}) {
  const [tab, setTab] = useState<"create" | "subscribe">("create");
  const [name, setName] = useState("");
  const [emoji, setEmoji] = useState("");
  const [visibility, setVisibility] = useState<"public" | "private">("private");
  const [portfolioId, setPortfolioId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const resetState = () => {
    setName("");
    setEmoji("");
    setPortfolioId("");
    setVisibility("private");
    setTab("create");
    setError(null);
  };

  return (
    <Modal
      open={open}
      onClose={() => {
        if (busy) return;
        resetState();
        onClose();
      }}
      title="New portfolio"
      onPrimary={async () => {
        if (busy) return;
        setError(null);
        try {
          setBusy(true);
          if (tab === "create") {
            await onCreate({
              name: name.trim() || "Untitled",
              emoji: emoji.trim() || undefined,
              visibility,
            });
            resetState();
            return;
          }
          if (!portfolioId.trim()) {
            setError("Portfolio ID is required");
            return;
          }
          await onSubscribe(portfolioId.trim());
          resetState();
        } catch (error: unknown) {
          setError(error instanceof Error ? error.message : tab === "create" ? "Failed to create" : "Failed to import");
        } finally {
          setBusy(false);
        }
      }}
      primaryLabel={busy ? "Please wait..." : tab === "create" ? "Create" : "Subscribe"}
    >
      <div className="flex gap-2">
        <Button
          variant={tab === "create" ? undefined : "outline"}
          onClick={() => {
            setError(null);
            setTab("create");
          }}
          disabled={busy}
        >
          Create
        </Button>
        <Button
          variant={tab === "subscribe" ? undefined : "outline"}
          onClick={() => {
            setError(null);
            setTab("subscribe");
          }}
          disabled={busy}
        >
          Subscribe
        </Button>
      </div>

      {error && <div className="text-sm text-red-400">{error}</div>}

      {tab === "create" ? (
        <div className="space-y-3">
          <div>
            <label className="block text-sm text-zinc-300">Name</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My portfolio"
              disabled={busy}
            />
          </div>
          <div>
            <label className="block text-sm text-zinc-300">Emoji icon (up to 3)</label>
            <Input
              value={emoji}
              onChange={(e) => setEmoji(e.target.value)}
              placeholder="***"
              maxLength={8}
              disabled={busy}
            />
          </div>
          <div className="flex items-center gap-4">
            <label className="text-sm text-zinc-300">Visibility</label>
            <label className="inline-flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="vis"
                checked={visibility === "private"}
                onChange={() => setVisibility("private")}
                disabled={busy}
              />
              Private
            </label>
            <label className="inline-flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="vis"
                checked={visibility === "public"}
                onChange={() => setVisibility("public")}
                disabled={busy}
              />
              Public
            </label>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="text-sm text-zinc-400">Paste portfolio ID</div>
          <Input
            value={portfolioId}
            onChange={(e) => setPortfolioId(e.target.value)}
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            disabled={busy}
          />
        </div>
      )}

      <div className="my-2 h-px w-full bg-gradient-to-r from-transparent via-white/10 to-transparent" />
    </Modal>
  );
}
