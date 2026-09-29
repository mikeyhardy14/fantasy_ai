"use client";

import { cn } from "@/lib/utils";
import { X } from "lucide-react";
import { useEffect, type ReactNode } from "react";

export function Pop({
  title,
  onClose,
  children,
  wide,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center p-3 sm:items-center">
      <button type="button" className="veil-enter absolute inset-0 bg-[#1c1916]/50" aria-label="Close" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="pop-title"
        className={cn(
          "sheet-enter relative z-10 flex max-h-[85vh] w-full flex-col overflow-hidden rounded-xl border border-white/10 bg-surface-raised shadow-xl",
          wide ? "max-w-4xl" : "max-w-lg",
        )}
      >
        <header className="flex items-center justify-between gap-3 border-b border-white/10 px-4 py-2">
          <h2 id="pop-title" className="truncate text-sm font-medium text-slate-100">
            {title}
          </h2>
          <button type="button" className="rounded-md p-1 text-slate-400 hover:bg-white/5 hover:text-slate-100" aria-label="Close" onClick={onClose}>
            <X className="h-4 w-4" />
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}
