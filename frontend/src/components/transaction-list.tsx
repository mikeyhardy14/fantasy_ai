import type { Transaction } from "@/lib/types";
import { cn, relativeTime } from "@/lib/utils";

export function TransactionList({ txs }: { txs: Transaction[] }) {
  return (
    <ul className="divide-y divide-surface-border/60">
      {txs.map((t) => (
        <li key={t.id} className={cn("px-5 py-2.5 text-xs", t.involves_user && "bg-brand-soft/10")} data-testid="transaction">
          <div className="flex items-center justify-between">
            <span className="font-medium uppercase tracking-wide text-slate-400">
              {t.type.replace("_", " ")}
              {t.faab_bid ? ` · $${t.faab_bid}` : ""}
            </span>
            <span className="text-slate-500">{t.week ? `Wk ${t.week}` : relativeTime(t.created_at)}</span>
          </div>
          <div className="mt-1 space-y-0.5 text-slate-300">
            {t.adds.map((a, i) => (
              <p key={`a${i}`}>
                <span className="text-emerald-300">+</span> {a.player_name ?? "Unknown"}{" "}
                <span className="text-slate-500">({a.position ?? "?"}) → {a.team_name ?? "?"}</span>
              </p>
            ))}
            {t.drops.map((d, i) => (
              <p key={`d${i}`}>
                <span className="text-red-300">−</span> {d.player_name ?? "Unknown"}{" "}
                <span className="text-slate-500">({d.position ?? "?"}) ← {d.team_name ?? "?"}</span>
              </p>
            ))}
            {!t.adds.length && !t.drops.length ? <p className="text-slate-500">{t.team_names.join(" ↔ ")}</p> : null}
          </div>
        </li>
      ))}
    </ul>
  );
}
