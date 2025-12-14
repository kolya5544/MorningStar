import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Plus, Home, Trash2, Pencil } from "lucide-react";

/* === API === */
import {
  getPortfolio,
  listAssets,
  addAsset,
  listTransactions,
  addTransaction,
  updateTransaction,
  deleteTransaction,
  getBybitTicker,
  type UUID,
  type AssetSummary,
  type TxItem,
  type TxCreate,
  type TxType,
  type BybitTicker,
} from "@/Api";

type UiAsset = { id: string; symbol: string; name: string; icon: string };

type UiTxKind = "BUY" | "SELL" | "DEPOSIT" | "WITHDRAW";

type UiTx = {
  id: string;
  ts: string; // ISO string
  kind: UiTxKind;
  qty: number; // amount in asset units
  price?: number; // optional (for BUY/SELL)
  note?: string;
};

function fmtNum(x: number, maxFrac = 8) {
  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits: maxFrac,
  }).format(x);
}

function fmtDt(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    year: "2-digit",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function kindLabel(k: UiTxKind) {
  if (k === "BUY") return "Buy";
  if (k === "SELL") return "Sell";
  if (k === "DEPOSIT") return "Deposit";
  return "Withdraw";
}

function kindClass(k: UiTxKind) {
  // аккуратные “бейджи” без кислотных цветов
  if (k === "BUY") return "bg-emerald-500/10 border-emerald-500/20 text-emerald-300";
  if (k === "SELL") return "bg-rose-500/10 border-rose-500/20 text-rose-300";
  if (k === "DEPOSIT") return "bg-sky-500/10 border-sky-500/20 text-sky-300";
  return "bg-amber-500/10 border-amber-500/20 text-amber-300";
}

function pickIcon(symbol: string, emoji?: string | null): string {
  if (emoji && emoji.trim()) return emoji;
  const s = symbol.toUpperCase();
  if (s === "BTC") return "₿";
  if (s === "ETH") return "◆";
  if (s === "SOL") return "◎";
  return "🪙";
}

function uiKindFromApiType(t: TxType): UiTxKind {
  if (t === "buy") return "BUY";
  if (t === "sell") return "SELL";
  if (t === "transfer_in") return "DEPOSIT";
  return "WITHDRAW";
}

function apiTypeFromUiKind(k: UiTxKind): TxType {
  if (k === "BUY") return "buy";
  if (k === "SELL") return "sell";
  if (k === "DEPOSIT") return "transfer_in";
  return "transfer_out";
}

function fromApiTx(t: TxItem): UiTx {
  return {
    id: t.id,
    ts: t.at,
    kind: uiKindFromApiType(t.type),
    qty: Number(t.quantity),
    price: t.price_usd != null ? Number(t.price_usd) : undefined,
    note: t.note ?? undefined,
  };
}

function toApiTxCreate(assetId: string, ui: UiTx): TxCreate {
  return {
    asset_id: assetId,
    type: apiTypeFromUiKind(ui.kind),
    quantity: String(ui.qty),
    price_usd: ui.price != null ? ui.price.toFixed(2) : null,
    fee_usd: null,
    at: ui.ts,
    note: ui.note ?? null,
    tx_hash: null,
  };
}

function pad2(n: number) {
  return String(n).padStart(2, "0");
}

function isoToLocalInput(iso: string): string {
  const d = new Date(iso);
  const yyyy = d.getFullYear();
  const mm = pad2(d.getMonth() + 1);
  const dd = pad2(d.getDate());
  const hh = pad2(d.getHours());
  const mi = pad2(d.getMinutes());
  return `${yyyy}-${mm}-${dd}T${hh}:${mi}`;
}

// datetime-local -> ISO (гарантированно как local time)
function localInputToIso(v: string): string {
  const [date, time] = v.split("T");
  const [y, m, d] = date.split("-").map(Number);
  const [hh, mi] = time.split(":").map(Number);
  const dt = new Date(y, m - 1, d, hh, mi, 0, 0);
  return dt.toISOString();
}

function nowLocalInput(): string {
  return isoToLocalInput(new Date().toISOString());
}

function isTrade(k: UiTxKind) {
  return k === "BUY" || k === "SELL";
}

function fmtUsd(x: number) {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(x);
}

export function PortfolioView(): JSX.Element {
  function openAddAsset() {
    setAssetModalErr(null);
    setAssetForm({ symbol: "", displayName: "", emoji: "" });
    setAssetModalOpen(true);
  }

  async function submitAsset() {
    if (!id) return;

    const symbol = assetForm.symbol.trim().toUpperCase();
    const display_name = assetForm.displayName.trim();
    const emoji = assetForm.emoji.trim();

    if (!symbol || symbol.length < 2 || symbol.length > 16) {
      setAssetModalErr("Symbol must be 2..16 characters");
      return;
    }
    if (display_name && display_name.length > 32) {
      setAssetModalErr("Display name max length is 32");
      return;
    }
    if (emoji && emoji.length > 8) {
      setAssetModalErr("Emoji max length is 8");
      return;
    }

    try {
      setAssetSaving(true);
      setAssetModalErr(null);

      const created = await addAsset(id, {
        symbol,
        display_name: display_name || null,
        emoji: emoji || null,
      });

      setAssets((prev) => [
        {
          id: created.id,
          symbol: created.symbol,
          name: created.display_name || created.symbol,
          icon: pickIcon(created.symbol, created.emoji),
        },
        ...prev,
      ]);

      setActive(created.id);
      setAssetModalOpen(false);
    } catch (e: any) {
      setAssetModalErr(e?.message ?? "Failed to add asset");
    } finally {
      setAssetSaving(false);
    }
  }

  function openCreateTx() {
    setTxEditingId(null);
    setTxModalErr(null);
    setTxForm({
      kind: "BUY",
      qty: "0.1",
      price: quote?.lastPrice ? quote.lastPrice : "",
      note: "",
      atLocal: nowLocalInput(),
    });
    setTxModalOpen(true);
  }

  function openEditTx(t: UiTx) {
    setTxEditingId(t.id);
    setTxModalErr(null);
    setTxForm({
      kind: t.kind,
      qty: String(t.qty),
      price: t.price != null ? String(t.price) : "",
      note: t.note ?? "",
      atLocal: isoToLocalInput(t.ts),
    });
    setTxModalOpen(true);
  }

  async function submitTx() {
    if (!id || !activeAsset) return;

    const qty = Number(txForm.qty);
    const price = txForm.price.trim() ? Number(txForm.price) : undefined;

    if (!Number.isFinite(qty) || qty <= 0) {
      setTxModalErr("Quantity must be > 0");
      return;
    }

    if (isTrade(txForm.kind) && (!price || !Number.isFinite(price) || price <= 0)) {
      setTxModalErr("Price is required for BUY/SELL and must be > 0");
      return;
    }

    const ui: UiTx = {
      id: txEditingId ?? "temp",
      ts: localInputToIso(txForm.atLocal),
      kind: txForm.kind,
      qty,
      price,
      note: txForm.note.trim() ? txForm.note.trim() : undefined,
    };

    try {
      setTxSaving(true);
      setTxModalErr(null);

      if (!txEditingId) {
        const created = await addTransaction(id, toApiTxCreate(activeAsset.id, ui));
        const mapped = fromApiTx(created);
        setTxByAsset((prev) => ({
          ...prev,
          [activeAsset.id]: [mapped, ...(prev[activeAsset.id] ?? [])],
        }));
      } else {
        const updated = await updateTransaction(id, txEditingId, toApiTxCreate(activeAsset.id, ui));
        const mapped = fromApiTx(updated);
        setTxByAsset((prev) => ({
          ...prev,
          [activeAsset.id]: (prev[activeAsset.id] ?? []).map((x) =>
            x.id === txEditingId ? mapped : x,
          ),
        }));
      }

      setTxModalOpen(false);
    } catch (e: any) {
      setTxModalErr(e?.message ?? "Failed to save transaction");
    } finally {
      setTxSaving(false);
    }
  }

  const { id } = useParams<{ id: UUID }>();
  const nav = useNavigate();

  const [portfolioTitle, setPortfolioTitle] = useState<string>(id ?? "");
  const [assets, setAssets] = useState<UiAsset[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busyAdd, setBusyAdd] = useState(false);
  const [txByAsset, setTxByAsset] = useState<Record<string, UiTx[]>>({});
  const [txLoading, setTxLoading] = useState(false);
  const [txErr, setTxErr] = useState<string | null>(null);
  const [txModalOpen, setTxModalOpen] = useState(false);
  const [txEditingId, setTxEditingId] = useState<string | null>(null); // null => create
  const [txSaving, setTxSaving] = useState(false);
  const [txModalErr, setTxModalErr] = useState<string | null>(null);

  const [assetModalOpen, setAssetModalOpen] = useState(false);
  const [assetSaving, setAssetSaving] = useState(false);
  const [assetModalErr, setAssetModalErr] = useState<string | null>(null);

  const [quote, setQuote] = useState<BybitTicker | null>(null);
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [quoteErr, setQuoteErr] = useState<string | null>(null);

  useEffect(() => {
    if (!active) {
      setQuote(null);
      return;
    }

    const a = assets.find((x) => x.id === active);
    if (!a?.symbol) {
      setQuote(null);
      return;
    }

    let cancelled = false;

    (async () => {
      try {
        setQuoteLoading(true);
        setQuoteErr(null);

        const q = await getBybitTicker(a.symbol, "spot");
        if (!cancelled) setQuote(q);
      } catch (e: any) {
        if (!cancelled) {
          setQuote(null);
          setQuoteErr(e?.message ?? "Failed to load market data");
        }
      } finally {
        if (!cancelled) setQuoteLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [active, assets]);

  const [assetForm, setAssetForm] = useState<{
    symbol: string;
    displayName: string;
    emoji: string;
  }>({ symbol: "", displayName: "", emoji: "" });

  const [txForm, setTxForm] = useState<{
    kind: UiTxKind;
    qty: string;
    price: string;
    note: string;
    atLocal: string; // yyyy-MM-ddTHH:mm
  }>({
    kind: "BUY",
    qty: "0.1",
    price: "",
    note: "",
    atLocal: "",
  });

  const activeAsset = useMemo(
    () => (active ? assets.find((a) => a.id === active) ?? null : null),
    [active, assets],
  );

  const activeTx = useMemo(() => (active ? txByAsset[active] ?? [] : []), [active, txByAsset]);

  const activeQty = useMemo(() => {
    if (!active) return 0;
    const tx = txByAsset[active] ?? [];
    return tx.reduce((acc, t) => {
      const sign = t.kind === "SELL" || t.kind === "WITHDRAW" ? -1 : 1;
      return acc + sign * t.qty;
    }, 0);
  }, [active, txByAsset]);

  const approxUsd = useMemo(() => {
    const px = quote?.lastPrice ? Number(quote.lastPrice) : null;
    if (!px || !Number.isFinite(px)) return null;
    return activeQty * px;
  }, [activeQty, quote?.lastPrice]);

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
          symbol: x.symbol,
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

  useEffect(() => {
    if (!id || !active) return;
    let cancelled = false;

    (async () => {
      try {
        setTxLoading(true);
        setTxErr(null);

        const tx = await listTransactions(id, active as UUID);
        if (cancelled) return;

        setTxByAsset((prev) => ({ ...prev, [active]: tx.map(fromApiTx) }));
      } catch (e: any) {
        if (!cancelled) setTxErr(e?.message ?? "Failed to load transactions");
      } finally {
        if (!cancelled) setTxLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [id, active]);

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
                          symbol: x.symbol,
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
            onClick={() => {
              if (!id) return;
              openAddAsset();
            }}
          >
            <Plus className="h-4 w-4 mr-2" /> Add asset
          </Button>
        </div>
      </aside>

      {/* Main panel */}
      <section className="min-h-screen p-6">
        {!activeAsset ? (
          <div className="h-full rounded-2xl border border-white/10 bg-zinc-950/40 p-6 flex items-center justify-center text-zinc-400">
            Select an asset on the left
          </div>
        ) : (
          <div className="h-full rounded-2xl border border-white/10 bg-zinc-950/60 p-6 flex flex-col">
            {/* Header */}
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-2xl border border-white/10 bg-white/5 flex items-center justify-center text-xl">
                    {activeAsset.icon}
                  </div>
                  <div>
                    <h1 className="text-3xl font-semibold leading-tight">{activeAsset.name}</h1>
                    <div className="text-sm text-zinc-400 mt-1">
                      Asset details • operations history
                    </div>
                  </div>
                </div>
              </div>

              {/* market info + кнопка */}
              <div className="flex items-start gap-3">
                <div className="text-right">
                  {quoteLoading ? (
                    <div className="text-xs text-zinc-400">Loading price…</div>
                  ) : quote ? (
                    <>
                      <div className="text-sm">
                        ${fmtNum(Number(quote.lastPrice), 8)}
                        <span className="text-xs text-zinc-400 ml-2">{quote.symbol}</span>
                      </div>
                      <div className="text-xs text-zinc-400">
                        24h: {(Number(quote.price24hPcnt) * 100).toFixed(2)}% • Turnover: $
                        {fmtNum(Number(quote.turnover24h), 0)}
                      </div>
                    </>
                  ) : (
                    <div className="text-xs text-zinc-500">{quoteErr ?? "No market data"}</div>
                  )}
                </div>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    if (!id || !activeAsset) return;
                    openCreateTx();
                  }}
                >
                  + Operation
                </Button>
              </div>
            </div>

            {/* Summary cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-6">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="text-sm text-zinc-400">Quantity</div>
                <div className="text-2xl font-semibold mt-1">
                  {fmtNum(activeQty)}{" "}
                  <span className="text-zinc-400 text-base font-normal">{activeAsset.name}</span>
                </div>
                <div className="text-sm text-zinc-400 mt-1">
                  {approxUsd == null ? "≈ —" : `≈ ${fmtUsd(approxUsd)}`}
                </div>
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="text-sm text-zinc-400">Operations</div>
                <div className="text-2xl font-semibold mt-1">{activeTx.length}</div>
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="text-sm text-zinc-400">Last activity</div>
                <div className="text-base mt-2 text-zinc-200">
                  {activeTx[0] ? (
                    fmtDt(activeTx[0].ts)
                  ) : (
                    <span className="text-zinc-400">No operations</span>
                  )}
                </div>
              </div>
            </div>

            {/* Operations list */}
            <div className="mt-6 flex-1 min-h-0 rounded-2xl border border-white/10 bg-black/20">
              <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
                <div>
                  <div className="font-medium">Operations</div>
                  <div className="text-xs text-zinc-400">Scrollable history for this asset</div>
                </div>
              </div>

              <div className="p-3 h-full overflow-y-auto space-y-2">
                {activeTx.length === 0 ? (
                  <div className="h-full flex items-center justify-center text-zinc-400 text-sm">
                    No operations yet. Add one to see it here.
                  </div>
                ) : (
                  activeTx.map((t) => (
                    <div
                      key={t.id}
                      className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 flex items-center justify-between gap-4"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span
                            className={`text-xs px-2 py-1 rounded-full border ${kindClass(t.kind)}`}
                          >
                            {kindLabel(t.kind)}
                          </span>
                          <span className="text-xs text-zinc-400">{fmtDt(t.ts)}</span>
                        </div>
                        {t.note ? (
                          <div className="text-sm text-zinc-200 mt-1 truncate">{t.note}</div>
                        ) : null}
                      </div>

                      <div className="text-right">
                        <div className="text-sm font-medium">
                          {t.kind === "SELL" || t.kind === "WITHDRAW" ? "−" : "+"}
                          {fmtNum(t.qty)}
                        </div>
                        {typeof t.price === "number" ? (
                          <div className="text-xs text-zinc-400">Price: {fmtNum(t.price, 2)}</div>
                        ) : (
                          <div className="text-xs text-zinc-500">—</div>
                        )}
                        <div className="flex items-center justify-end gap-2 mt-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => openEditTx(t)}
                            title="Edit"
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>

                          <Button
                            variant="outline"
                            size="sm"
                            onClick={async () => {
                              if (!id || !activeAsset) return;
                              if (!confirm("Delete this transaction?")) return;

                              try {
                                await deleteTransaction(id, t.id);
                                setTxByAsset((prev) => ({
                                  ...prev,
                                  [activeAsset.id]: (prev[activeAsset.id] ?? []).filter(
                                    (x) => x.id !== t.id,
                                  ),
                                }));
                              } catch (e: any) {
                                alert(e?.message ?? "Failed to delete transaction");
                              }
                            }}
                            title="Delete"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}
      </section>

      {txModalOpen && (
        <div className="fixed inset-0 z-50">
          <div
            className="absolute inset-0 bg-black/70"
            onClick={() => !txSaving && setTxModalOpen(false)}
          />
          <div className="absolute inset-0 flex items-center justify-center p-4">
            <div className="w-full max-w-md rounded-2xl border border-white/10 bg-zinc-950 text-white shadow-xl">
              <div className="px-5 py-4 border-b border-white/10">
                <div className="text-lg font-semibold">
                  {txEditingId ? "Edit operation" : "New operation"}
                </div>
                <div className="text-xs text-zinc-400 mt-1">{activeAsset?.name}</div>
              </div>

              <div className="px-5 py-4 space-y-3">
                {txModalErr && <div className="text-sm text-red-400">{txModalErr}</div>}

                <label className="block">
                  <div className="text-xs text-zinc-400 mb-1">Type</div>
                  <select
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 outline-none"
                    value={txForm.kind}
                    onChange={(e) => {
                      const k = e.target.value as UiTxKind;
                      setTxForm((p) => ({
                        ...p,
                        kind: k,
                        price: isTrade(k) ? p.price || quote?.lastPrice || "" : "",
                      }));
                    }}
                    disabled={txSaving}
                  >
                    <option value="BUY">Buy</option>
                    <option value="SELL">Sell</option>
                    <option value="DEPOSIT">Deposit</option>
                    <option value="WITHDRAW">Withdraw</option>
                  </select>
                </label>

                <div className="grid grid-cols-2 gap-3">
                  <label className="block">
                    <div className="text-xs text-zinc-400 mb-1">Quantity</div>
                    <input
                      className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 outline-none"
                      value={txForm.qty}
                      onChange={(e) => setTxForm((p) => ({ ...p, qty: e.target.value }))}
                      disabled={txSaving}
                      inputMode="decimal"
                    />
                  </label>

                  <label className="block">
                    <div className="text-xs text-zinc-400 mb-1">Price USD</div>
                    <input
                      className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 outline-none disabled:opacity-40"
                      value={txForm.price}
                      onChange={(e) => setTxForm((p) => ({ ...p, price: e.target.value }))}
                      disabled={txSaving || !isTrade(txForm.kind)}
                      inputMode="decimal"
                      placeholder={isTrade(txForm.kind) ? "e.g. 42000" : "—"}
                    />
                  </label>
                </div>

                <label className="block">
                  <div className="text-xs text-zinc-400 mb-1">Date & time</div>
                  <input
                    type="datetime-local"
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 outline-none"
                    value={txForm.atLocal}
                    onChange={(e) => setTxForm((p) => ({ ...p, atLocal: e.target.value }))}
                    disabled={txSaving}
                  />
                </label>

                <label className="block">
                  <div className="text-xs text-zinc-400 mb-1">Note</div>
                  <input
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 outline-none"
                    value={txForm.note}
                    onChange={(e) => setTxForm((p) => ({ ...p, note: e.target.value }))}
                    disabled={txSaving}
                    placeholder="optional"
                  />
                </label>
              </div>

              <div className="px-5 py-4 border-t border-white/10 flex justify-end gap-2">
                <Button variant="outline" onClick={() => setTxModalOpen(false)} disabled={txSaving}>
                  Cancel
                </Button>
                <Button onClick={submitTx} disabled={txSaving}>
                  {txEditingId ? "Save" : "Add"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {assetModalOpen && (
        <div className="fixed inset-0 z-50">
          <div
            className="absolute inset-0 bg-black/70"
            onClick={() => !assetSaving && setAssetModalOpen(false)}
          />
          <div className="absolute inset-0 flex items-center justify-center p-4">
            <div className="w-full max-w-md rounded-2xl border border-white/10 bg-zinc-950 text-white shadow-xl">
              <div className="px-5 py-4 border-b border-white/10">
                <div className="text-lg font-semibold">New asset</div>
                <div className="text-xs text-zinc-400 mt-1">{portfolioTitle}</div>
              </div>

              <div className="px-5 py-4 space-y-3">
                {assetModalErr && <div className="text-sm text-red-400">{assetModalErr}</div>}

                <label className="block">
                  <div className="text-xs text-zinc-400 mb-1">Symbol</div>
                  <input
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 outline-none"
                    value={assetForm.symbol}
                    onChange={(e) => setAssetForm((p) => ({ ...p, symbol: e.target.value }))}
                    disabled={assetSaving}
                    placeholder="BTC"
                  />
                </label>

                <label className="block">
                  <div className="text-xs text-zinc-400 mb-1">Display name</div>
                  <input
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 outline-none"
                    value={assetForm.displayName}
                    onChange={(e) => setAssetForm((p) => ({ ...p, displayName: e.target.value }))}
                    disabled={assetSaving}
                    placeholder="Bitcoin (optional)"
                  />
                </label>

                <label className="block">
                  <div className="text-xs text-zinc-400 mb-1">Emoji</div>
                  <input
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 outline-none"
                    value={assetForm.emoji}
                    onChange={(e) => setAssetForm((p) => ({ ...p, emoji: e.target.value }))}
                    disabled={assetSaving}
                    placeholder="🪙 (optional)"
                  />
                </label>

                <div className="text-xs text-zinc-400">
                  Preview:{" "}
                  <span className="text-zinc-200">
                    {pickIcon(assetForm.symbol || "X", assetForm.emoji || undefined)}{" "}
                    {(assetForm.displayName || assetForm.symbol || "Asset").trim()}
                  </span>
                </div>
              </div>

              <div className="px-5 py-4 border-t border-white/10 flex justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => setAssetModalOpen(false)}
                  disabled={assetSaving}
                >
                  Cancel
                </Button>
                <Button onClick={submitAsset} disabled={assetSaving}>
                  Add
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
