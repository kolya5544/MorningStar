import React, { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Plus, Home } from "lucide-react";

export function PortfolioView(): JSX.Element {
  const { id } = useParams();
  const nav = useNavigate();

  const assets = useMemo(
    () => [
      { id: "btc", name: "Bitcoin", icon: "₿" },
      { id: "eth", name: "Ethereum", icon: "◆" },
      { id: "sol", name: "Solana", icon: "◎" },
    ],
    [],
  );

  const [active, setActive] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-black text-white grid grid-cols-[280px_1fr]">
      {/* Sidebar */}
      <aside className="border-r border-white/10 bg-zinc-950/60 flex flex-col">
        <div className="h-16 px-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <img src="/morningstar.svg" alt="MorningStar" className="h-7 w-7" />
            <span className="font-medium">{id}</span>
          </div>
          <Button variant="outline" size="sm" onClick={() => nav("/dashboard")}>
            {" "}
            <Home className="h-4 w-4 mr-2" /> Home
          </Button>
        </div>
        <div className="h-px w-full bg-white/10" />
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {assets.map((a) => (
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
        </div>
        <div className="p-2">
          <Button className="w-full" variant="outline">
            {" "}
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
