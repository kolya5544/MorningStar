import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Home, LogOut, Shield } from "lucide-react";
import { Modal } from "@/components/ui/modal";
import { clearAccessToken, isAuthError, authMe, type Role } from "@/Api";
import {
  listPortfolios,
  createPortfolio,
  importPortfolio,
  type PortfolioSummary as SPortfolioSummary,
  type PortfolioDetail as SPortfolioDetail,
  type Visibility,
} from "@/Api";

export type Portfolio = {
  id: string;
  name: string;
  emoji: string;
  balance: number;
  pnlDay: number;
  kind: "personal" | "subscribed";
  visibility?: "public" | "private";
};

function fmtMoney(v: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(v);
}

function mapSummary(p: SPortfolioSummary): Portfolio {
  return {
    id: p.id,
    name: p.name,
    emoji: p.emoji ?? "[P]",
    balance: Number(p.balance_usd ?? "0"),
    pnlDay: Number(p.pnl_day_usd ?? "0"),
    kind: p.kind,
    visibility: p.visibility ?? undefined,
  };
}

export default function Dashboard(): JSX.Element {
  const nav = useNavigate();
  const [items, setItems] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [openAdd, setOpenAdd] = useState(false);
  const [role, setRole] = useState<Role | null>(null);
  const [meId, setMeId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await authMe();
        if (!cancelled) {
          setRole(me.role);
          setMeId(me.id);
        }
      } catch {
        // Ignore; auth failures are handled by portfolio loading below.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        setErr(null);
        const data = await listPortfolios();
        if (!cancelled) {
          const filtered =
            role === "manager" && meId ? data.filter((p) => p.owner_id === meId) : data;
          setItems(filtered.map(mapSummary));
        }
      } catch (e: any) {
        if (isAuthError(e)) {
          clearAccessToken();
          nav("/", { replace: true });
          return;
        }
        if (!cancelled) setErr(e?.message ?? "Failed to load");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [nav, role, meId]);

  const reloadPortfolios = async () => {
    setLoading(true);
    setErr(null);
    try {
      const data = await listPortfolios();
      const filtered =
        role === "manager" && meId ? data.filter((p) => p.owner_id === meId) : data;
      setItems(filtered.map(mapSummary));
    } catch (e: any) {
      if (isAuthError(e)) {
        clearAccessToken();
        nav("/", { replace: true });
        return;
      }
      setErr(e?.message ?? "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    clearAccessToken();
    nav("/", { replace: true });
  };

  return (
    <div className="min-h-screen bg-black text-white">
      <header className="sticky top-0 z-20 w-full backdrop-blur bg-black/30">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center gap-3">
              <img
                src="/morningstar.svg"
                alt="MorningStar"
                className="h-8 w-8 shrink-0 align-middle"
              />
              <span className="text-lg font-semibold tracking-wide">MorningStar</span>
              {role && role !== "user" && (
                <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-xs uppercase tracking-wide text-zinc-300">
                  {role}
                </span>
              )}
            </div>
            <nav className="flex items-center gap-2">
              <Button variant="outline" onClick={() => nav("/dashboard")}>
                <Home className="mr-2 h-4 w-4" /> Home
              </Button>
              {(role === "manager" || role === "admin") && (
                <Button variant="outline" onClick={() => nav("/control-panel")}>
                  <Shield className="mr-2 h-4 w-4" /> Control Panel
                </Button>
              )}
              <Button variant="outline" onClick={logout}>
                <LogOut className="mr-2 h-4 w-4" /> Logout
              </Button>
            </nav>
          </div>
        </div>
        <div className="h-px w-full bg-gradient-to-r from-transparent via-[#16335f] to-transparent opacity-50" />
      </header>

      <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Your portfolios</h1>
          {role && (
            <Button onClick={() => setOpenAdd(true)}>
              <Plus className="mr-2 h-4 w-4" /> New portfolio
            </Button>
          )}
        </div>

        {loading && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="h-[140px] rounded-2xl border border-white/10 bg-zinc-950/80 p-4 animate-pulse"
              />
            ))}
          </div>
        )}

        {!loading && err && (
          <div className="text-sm text-red-400">
            {err}{" "}
            <button className="underline decoration-dotted" onClick={() => void reloadPortfolios()}>
              retry
            </button>
          </div>
        )}

        {!loading && !err && items.length === 0 && (
          <div className="text-zinc-400">No portfolios yet. Create the first one.</div>
        )}

        {!loading && !err && items.length > 0 && (
          <div className="grid grid-cols-1 gap-4 place-items-stretch sm:grid-cols-2 lg:grid-cols-3">
            {items.map((p) => (
              <button
                key={p.id}
                onClick={() => nav(`/dashboard/${p.id}`)}
                className="group flex flex-col rounded-2xl border border-white/10 bg-zinc-950/80 p-4 text-left transition hover:bg-white/5"
              >
                <div className="flex items-start justify-between">
                  <div className="text-2xl leading-none" aria-hidden>
                    {p.emoji}
                  </div>
                  <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-xs text-zinc-300">
                    {p.kind}
                    {p.kind === "personal" && p.visibility ? ` - ${p.visibility}` : ""}
                  </span>
                </div>
                <div className="mt-3 line-clamp-1 text-base font-medium">{p.name}</div>
                <div className="mt-1 text-sm text-zinc-400">{fmtMoney(p.balance)}</div>
                <div
                  className={`mt-4 text-sm font-medium ${
                    p.pnlDay >= 0 ? "text-emerald-400" : "text-red-400"
                  }`}
                >
                  {p.pnlDay >= 0 ? "+" : ""}
                  {fmtMoney(p.pnlDay)} today
                </div>
              </button>
            ))}
          </div>
        )}
      </main>

      <AddPortfolioModal
        open={openAdd}
        onClose={() => setOpenAdd(false)}
        onCreate={async (data) => {
          const created: SPortfolioDetail = await createPortfolio({
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
        } catch (e: any) {
          setError(e?.message ?? (tab === "create" ? "Failed to create" : "Failed to import"));
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
