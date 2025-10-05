import React, { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Home } from "lucide-react";
import { Modal } from "@/components/ui/modal";

export type Portfolio = {
  id: string;
  name: string;
  emoji: string; // up to 3 emojis
  balance: number; // USD for mock
  pnlDay: number; // daily PnL USD
  kind: "personal" | "subscribed";
  visibility?: "public" | "private"; // only for personal
};

function fmtMoney(v: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(v);
}

export default function Dashboard(): JSX.Element {
  const nav = useNavigate();

  const initial: Portfolio[] = useMemo(
    () => [
      {
        id: "p1",
        name: "Main HODL",
        emoji: "🚀",
        balance: 48250,
        pnlDay: 620,
        kind: "personal",
        visibility: "private",
      },
      {
        id: "p2",
        name: "DeFi",
        emoji: "🧪",
        balance: 17340,
        pnlDay: -140,
        kind: "personal",
        visibility: "public",
      },
      {
        id: "p3",
        name: "Alt bets",
        emoji: "🎯🔥",
        balance: 8920,
        pnlDay: 80,
        kind: "personal",
        visibility: "private",
      },
    ],
    [],
  );

  const [items, setItems] = useState<Portfolio[]>(initial);
  const [openAdd, setOpenAdd] = useState(false);

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
        <h1 className="text-2xl font-semibold mb-6">Your portfolios</h1>

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

          {/* Add new portfolio card */}
          <button
            onClick={() => setOpenAdd(true)}
            className="rounded-2xl border-2 border-dashed border-[#16335f] hover:border-[#0e2a54] bg-zinc-950/60 p-4 flex items-center justify-center min-h-[140px]"
          >
            <span className="inline-flex items-center gap-2 text-zinc-300">
              <Plus className="h-5 w-5" />
              New portfolio
            </span>
          </button>
        </div>
      </main>

      {/* Create / Subscribe modal */}
      <AddPortfolioModal
        open={openAdd}
        onClose={() => setOpenAdd(false)}
        onCreate={(data) => {
          const id = `p${Date.now()}`;
          setItems((prev) => [
            {
              id,
              name: data.name,
              emoji: data.emoji || "📦",
              balance: 0,
              pnlDay: 0,
              kind: "personal",
              visibility: data.visibility,
            },
            ...prev,
          ]);
          setOpenAdd(false);
        }}
        onSubscribe={(guid) => {
          // mock: navigate to subscribed portfolio; real logic later
          const id = `s-${guid.slice(0, 6)}`;
          setItems((prev) => [
            {
              id,
              name: `Subscribed ${guid.slice(0, 6)}`,
              emoji: "⭐",
              balance: 0,
              pnlDay: 0,
              kind: "subscribed",
            },
            ...prev,
          ]);
          setOpenAdd(false);
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
  onCreate: (data: CreatePayload) => void;
  onSubscribe: (guid: string) => void;
}) {
  const [tab, setTab] = useState<"create" | "subscribe">("create");
  const [name, setName] = useState("");
  const [emoji, setEmoji] = useState("");
  const [visibility, setVisibility] = useState<"public" | "private">("private");
  const [guid, setGuid] = useState("");

  return (
    <Modal
      open={open}
      onClose={() => {
        setName("");
        setEmoji("");
        setGuid("");
        setVisibility("private");
        setTab("create");
        onClose();
      }}
      title="New portfolio"
      onPrimary={() => {
        if (tab === "create")
          onCreate({ name: name.trim() || "Untitled", emoji: emoji.trim(), visibility });
        else if (guid.trim()) onSubscribe(guid.trim());
      }}
      primaryLabel={tab === "create" ? "Create" : "Subscribe"}
    >
      {/* Tabs mimic via two buttons */}
      <div className="flex gap-2">
        <Button variant={tab === "create" ? undefined : "outline"} onClick={() => setTab("create")}>
          Create
        </Button>
        <Button
          variant={tab === "subscribe" ? undefined : "outline"}
          onClick={() => setTab("subscribe")}
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
            />
          </div>
          <div>
            <label className="block text-sm text-zinc-300">Emoji icon (up to 3)</label>
            <Input
              value={emoji}
              onChange={(e) => setEmoji(e.target.value)}
              placeholder="🚀🚀🚀"
              maxLength={6}
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
              />
              Private
            </label>
            <label className="inline-flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="vis"
                checked={visibility === "public"}
                onChange={() => setVisibility("public")}
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
          />
        </div>
      )}

      {/* Visual separator */}
      <div className="my-2 h-px w-full bg-gradient-to-r from-transparent via-white/10 to-transparent" />
    </Modal>
  );
}
