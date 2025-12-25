import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Home } from "lucide-react";
import { Modal } from "@/components/ui/modal";
import { clearAccessToken, isAuthError } from "@/Api";

// === API ===
import {
  listPortfolios,
  createPortfolio,
  importPortfolio,
  type PortfolioSummary as SPortfolioSummary,
  type PortfolioDetail as SPortfolioDetail,
  type Visibility,
} from "@/Api"; // твой Api.tsx

export type Portfolio = {
  id: string;
  name: string;
  emoji: string; // up to 3 emojis
  balance: number; // USD
  pnlDay: number; // USD
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

// server -> ui
function mapSummary(p: SPortfolioSummary): Portfolio {
  return {
    id: p.id,
    name: p.name,
    emoji: p.emoji ?? "📦",
    balance: Number(p.balance_usd ?? "0"),
    pnlDay: Number(p.pnl_day_usd ?? "0"),
    kind: p.kind, // "personal" | "subscribed"
    visibility: p.visibility ?? undefined,
  };
}

export default function Dashboard(): JSX.Element {
  const nav = useNavigate();

  const [items, setItems] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const [openAdd, setOpenAdd] = useState(false);

  // load from API once
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        setErr(null);
        const data = await listPortfolios();
        if (!cancelled) setItems(data.map(mapSummary));
      } catch (e: any) {
        if (isAuthError(e)) {
          clearAccessToken();
          nav("/", { replace: true });
          return;
        }
        setErr(e?.message ?? "Failed to load");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="min-h-screen bg-black text-white">
      {/* Header */}
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
            </div>
            <nav className="flex items-center gap-2">
              <Button variant="outline" onClick={() => nav("/dashboard")}>
                <Home className="mr-2 h-4 w-4" /> Home
              </Button>
            </nav>
          </div>
        </div>
        <div className="h-px w-full bg-gradient-to-r from-transparent via-[#16335f] to-transparent opacity-50" />
      </header>

      {/* Home grid */}
      <main className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-10">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-semibold">Your portfolios</h1>
          <Button onClick={() => setOpenAdd(true)}>
            <Plus className="h-4 w-4 mr-2" /> New portfolio
          </Button>
        </div>

        {/* states */}
        {loading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="rounded-2xl border border-white/10 bg-zinc-950/80 p-4 animate-pulse h-[140px]"
              />
            ))}
          </div>
        )}

        {!loading && err && (
          <div className="text-sm text-red-400">
            {err}{" "}
            <button
              className="underline decoration-dotted"
              onClick={() => {
                setLoading(true);
                setErr(null);
                listPortfolios()
                  .then((d) => setItems(d.map(mapSummary)))
                  .catch((e) => setErr(e?.message ?? "Failed to load"))
                  .finally(() => setLoading(false));
              }}
            >
              retry
            </button>
          </div>
        )}

        {!loading && !err && items.length === 0 && (
          <div className="text-zinc-400">No portfolios yet. Create the first one.</div>
        )}

        {!loading && !err && items.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 place-items-stretch">
            {items.map((p) => (
              <button
                key={p.id}
                onClick={() => nav(`/dashboard/${p.id}`)}
                className="group text-left rounded-2xl border border-white/10 bg-zinc-950/80 p-4 hover:bg-white/5 transition flex flex-col"
              >
                <div className="flex items-start justify-between">
                  <div className="text-2xl leading-none" aria-hidden>
                    {p.emoji}
                  </div>
                  <span className="text-xs rounded-full px-2 py-0.5 bg-white/5 border border-white/10 text-zinc-300">
                    {p.kind}
                    {p.kind === "personal" && p.visibility ? ` · ${p.visibility}` : ""}
                  </span>
                </div>
                <div className="mt-3 font-medium text-base line-clamp-1">{p.name}</div>
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

      {/* Create / Subscribe modal */}
      <AddPortfolioModal
        open={openAdd}
        onClose={() => setOpenAdd(false)}
        onCreate={async (data) => {
          // POST /api/v1/portfolios
          try {
            const created: SPortfolioDetail = await createPortfolio({
              name: data.name,
              emoji: data.emoji,
              visibility: data.visibility as Visibility,
            });
            const ui = mapSummary(created);
            setItems((prev) => [ui, ...prev]);
            setOpenAdd(false);
            // по желанию: перейти сразу в портфель
            // nav(`/dashboard/${created.id}`);
          } catch (e: any) {
            alert(e?.message ?? "Failed to create");
          }
        }}
        onSubscribe={async (guid) => {
          try {
            const created = await importPortfolio(guid as any);
            const ui = mapSummary(created);
            setItems((prev) => [ui, ...prev]);
            setOpenAdd(false);
          } catch (e: any) {
            alert(e?.message ?? "Failed to import");
          }
        }}
      />
    </div>
  );
}

// ---------------------- AddPortfolioModal ----------------------

type CreatePayload = { name: string; emoji?: string; visibility: "public" | "private" };

function AddPortfolioModal({
  open,
  onClose,
  onCreate,
  onSubscribe,
}: {
  open: boolean;
  onClose: () => void;
  onCreate: (data: CreatePayload) => void | Promise<void>;
  onSubscribe: (guid: string) => void | Promise<void>;
}) {
  const [tab, setTab] = useState<"create" | "subscribe">("create");
  const [name, setName] = useState("");
  const [emoji, setEmoji] = useState("");
  const [visibility, setVisibility] = useState<"public" | "private">("private");
  const [guid, setGuid] = useState("");
  const [busy, setBusy] = useState(false);

  return (
    <Modal
      open={open}
      onClose={() => {
        if (busy) return;
        setName("");
        setEmoji("");
        setGuid("");
        setVisibility("private");
        setTab("create");
        onClose();
      }}
      title="New portfolio"
      onPrimary={async () => {
        if (busy) return;
        if (tab === "create") {
          setBusy(true);
          await onCreate({
            name: name.trim() || "Untitled",
            emoji: emoji.trim(),
            visibility,
          });
          setBusy(false);
        } else if (guid.trim()) {
          setBusy(true);
          await onSubscribe(guid.trim());
          setBusy(false);
        }
      }}
      primaryLabel={busy ? "Please wait…" : tab === "create" ? "Create" : "Subscribe"}
    >
      {/* Tabs mimic via two buttons */}
      <div className="flex gap-2">
        <Button
          variant={tab === "create" ? undefined : "outline"}
          onClick={() => setTab("create")}
          disabled={busy}
        >
          Create
        </Button>
        <Button
          variant={tab === "subscribe" ? undefined : "outline"}
          onClick={() => setTab("subscribe")}
          disabled={busy}
        >
          Subscribe
        </Button>
      </div>

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
              placeholder="🚀🚀🚀"
              maxLength={6}
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
          <div className="text-sm text-zinc-400">Paste portfolio GUID</div>
          <Input
            value={guid}
            onChange={(e) => setGuid(e.target.value)}
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            disabled={busy}
          />
        </div>
      )}

      <div className="my-2 h-px w-full bg-gradient-to-r from-transparent via-white/10 to-transparent" />
    </Modal>
  );
}
