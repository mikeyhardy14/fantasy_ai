import type { Recommendation, RecommendationType } from "@/lib/types";
import { cn } from "@/lib/utils";
import { PriorityBadge } from "./ui/badge";

const TYPE_LABEL: Record<RecommendationType, string> = {
  START_SIT: "Start / Sit",
  ADD_PLAYER: "Add",
  DROP_PLAYER: "Drop",
  WAIVER_TARGET: "Waiver",
  TRADE_TARGET: "Trade",
  INJURY_ALERT: "Injury",
  BYE_WEEK: "Bye week",
  ROSTER_WEAKNESS: "Weakness",
};

export function RecommendationCard({ rec, compact = false }: { rec: Recommendation; compact?: boolean }) {
  const label = TYPE_LABEL[rec.type] ?? rec.type;
  return (
    <div className={cn("border-b border-surface-border py-3", compact && "py-2")} data-testid="recommendation">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</span>
          <PriorityBadge priority={rec.priority} />
        </div>
        <p className="mt-0.5 text-sm font-medium text-slate-100">{rec.title}</p>
        {!compact ? <p className="mt-1 text-xs leading-relaxed text-slate-400">{rec.reason}</p> : null}
      </div>
    </div>
  );
}

export function RecommendationList({ recs, limit, compact }: { recs: Recommendation[]; limit?: number; compact?: boolean }) {
  const items = limit ? recs.slice(0, limit) : recs;
  return (
    <div className="space-y-2">
      {items.map((r, i) => (
        <RecommendationCard key={`${r.type}-${r.title}-${i}`} rec={r} compact={compact} />
      ))}
    </div>
  );
}
