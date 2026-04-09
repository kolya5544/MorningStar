import React from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";

type Props = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  onPrimary: () => void;
  primaryLabel?: string;
};

export function Modal({
  open,
  onClose,
  title,
  children,
  onPrimary,
  primaryLabel = "Continue",
}: Props) {
  if (!open) return null;
  const titleId = `modal-title-${title.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative z-[101] w-full max-w-md rounded-2xl border border-white/10 bg-zinc-950 p-5 shadow-xl"
      >
        <div className="flex items-center justify-between">
          <h2 id={titleId} className="text-lg font-semibold">
            {title}
          </h2>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-white/5">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="mt-4 space-y-4">{children}</div>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={onPrimary}>{primaryLabel}</Button>
        </div>
      </div>
    </div>
  );
}
