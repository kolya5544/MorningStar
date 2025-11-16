import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Plus, Home } from "lucide-react";

/* === API === */
import { getPortfolio, listAssets, addAsset, type UUID, type AssetSummary } from "@/Api";

type UiAsset = { id: string; name: string; icon: string };

function pickIcon(symbol: string, emoji?: string | null): string {
  if (emoji && emoji.trim()) return emoji;
  const s = symbol.toUpperCase();
  if (s === "BTC") return "₿";
  if (s === "ETH") return "◆";
  if (s === "SOL") return "◎";
  return "🪙";
}

export function PortfolioView(): JSX.Element {
  const { id } = useParams<{ id: UUID }>();
  const nav = useNavigate();

  const [portfolioTitle, setPortfolioTitle] = useState<string>(id ?? "");
  const [assets, setAssets] = useState<UiAsset[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busyAdd, setBusyAdd] = useState(false);

  // load portfolio + assets
  useEffect(() => {
    if (!id) return;
    let cancelled = false;

    (async () => {
      try {
        setLoading(true);
        setErr(null);

        const [p, a] = await Promise.all([getPortfolio(id), listAssets(id)]);
        if (cancelled) return;

        setPortfolioTitle(p.name);
        const ui: UiAsset[] = a.map((x: AssetSummary) => ({
          id: x.id,
          name: x.display_name || x.symbol,
          icon: pickIcon(x.symbol, x.emoji),
        }));
        setAssets(ui);
      } catch (e: any) {
        if (!cancelled) setErr(e?.message ?? "Failed to load");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [id]);

  return (
    <div className="min-h-screen bg-black text-white grid grid-cols-[280px_1fr]">
      {/* Sidebar */}
      <aside className="border-r border-white/10 bg-zinc-950/60 flex flex-col">
        <div className="h-16 px-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <img src="/morningstar.svg" alt="MorningStar" className="h-7 w-7" />
            <span className="font-medium line-clamp-1" title={portfolioTitle}>
              {portfolioTitle || id}
            </span>
          </div>
          <Button variant="outline" size="sm" onClick={() => nav("/dashboard")}>
            <Home className="h-4 w-4 mr-2" /> Home
          </Button>
        </div>
        <div className="h-px w-full bg-white/10" />

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {loading && (
            <>
              <div className="h-9 rounded-xl border border-white/10 bg-white/5 animate-pulse" />
              <div className="h-9 rounded-xl border border-white/10 bg-white/5 animate-pulse" />
              <div className="h-9 rounded-xl border border-white/10 bg-white/5 animate-pulse" />
            </>
          )}

          {!loading && err && (
            <div className="text-sm text-red-400 px-1">
              {err}{" "}
              <button
                className="underline decoration-dotted"
                onClick={() => {
                  if (!id) return;
                  setLoading(true);
                  setErr(null);
                  Promise.all([getPortfolio(id), listAssets(id)])
                    .then(([p, a]) => {
                      setPortfolioTitle(p.name);
                      setAssets(
                        a.map((x) => ({
                          id: x.id,
                          name: x.display_name || x.symbol,
                          icon: pickIcon(x.symbol, x.emoji),
                        })),
                      );
                    })
                    .catch((e) => setErr(e?.message ?? "Failed to load"))
                    .finally(() => setLoading(false));
                }}
              >
                retry
              </button>
            </div>
          )}

          {!loading &&
            !err &&
            assets.map((a) => (
              <button
                key={a.id}
                onClick={() => setActive(a.id)}
                className={`w-full text-left rounded-xl px-3 py-2 border ${
                  active === a.id
                    ? "bg-white/10 border-white/20"
                    : "bg-transparent border-white/10 hover:bg-white/5"
                }`}
              >
                <span className="mr-2" aria-hidden>
                  {a.icon}
                </span>
                {a.name}
              </button>
            ))}

          {!loading && !err && assets.length === 0 && (
            <div className="text-sm text-zinc-400 px-1">No assets yet.</div>
          )}
        </div>

        <div className="p-2">
          <Button
            className="w-full"
            variant="outline"
            disabled={busyAdd || !id}
            onClick={async () => {
              if (!id) return;
              // минимальный UX без модалки: два prompt
              const symbol = prompt("Asset symbol (e.g., BTC):", "BTC")?.trim();
              if (!symbol) return;
              const emoji = prompt("Emoji (optional, up to 3):", "🪙")?.trim() || undefined;

              try {
                setBusyAdd(true);
                const created = await addAsset(id, {
                  symbol,
                  display_name: symbol.toUpperCase(),
                  emoji,
                });
                setAssets((prev) => [
                  {
                    id: created.id,
                    name: created.display_name || created.symbol,
                    icon: pickIcon(created.symbol, created.emoji),
                  },
                  ...prev,
                ]);
                setActive(created.id);
              } catch (e: any) {
                alert(e?.message ?? "Failed to add asset");
              } finally {
                setBusyAdd(false);
              }
            }}
          >
            <Plus className="h-4 w-4 mr-2" /> Add asset
          </Button>
        </div>
      </aside>

      {/* Main panel */}
      <section className="min-h-screen p-6">
        {active ? (
          <div className="h-full rounded-2xl border border-white/10 bg-zinc-950/60 p-6">
            <h1 className="text-xl font-semibold">{assets.find((a) => a.id === active)?.name}</h1>
            <p className="text-zinc-400 mt-2">
              Панель актива. Здесь позже будут графики, позиции и операции.
            </p>
          </div>
        ) : (
          <div className="h-full rounded-2xl border border-white/10 bg-zinc-950/40 p-6 flex items-center justify-center text-zinc-400">
            Select an asset on the left
          </div>
        )}
      </section>
    </div>
  );
}
