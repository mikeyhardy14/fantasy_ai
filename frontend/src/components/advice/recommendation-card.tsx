import { MentionText } from "@/components/player/player-mentions";
import { Button } from "@/components/ui/button";
import { PriorityBadge } from "@/components/ui/badge";
import { recAction, recActionLabel } from "@/lib/rec-actions";
import type { Recommendation, RecommendationType } from "@/lib/types";
import { cn } from "@/lib/utils";

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

export function RecommendationCard({
  rec,
  compact = false,
  onDo,
  onDisable,
  pending = false,
}: {
  rec: Recommendation;
  compact?: boolean;
  onDo?: (rec: Recommendation) => void;
  onDisable?: (rec: Recommendation) => void;
  pending?: boolean;
}) {
  const label = TYPE_LABEL[rec.type] ?? rec.type;
  const action = recAction(rec);
  return (
    <div className={cn("border-b border-surface-border py-3", compact && "py-2")} data-testid="recommendation">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</span>
            <PriorityBadge priority={rec.priority} />
          </div>
          <p className="mt-0.5 text-sm font-medium text-slate-100"><MentionText text={rec.title} /></p>
          {!compact ? <p className="mt-1 text-xs leading-relaxed text-slate-400"><MentionText text={rec.reason} /></p> : null}
        </div>
        {onDo || onDisable ? (
          <div className="flex shrink-0 flex-col gap-1">
            {onDo && action ? (
              <Button size="sm" data-testid="rec-do" disabled={pending} onClick={() => onDo(rec)}>
                {recActionLabel(rec)}
              </Button>
            ) : null}
            {onDisable ? (
              <Button size="sm" variant="ghost" data-testid="rec-disable" disabled={pending} onClick={() => onDisable(rec)}>
                Disable
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function RecommendationList({
  recs,
  limit,
  compact,
  onDo,
  onDisable,
  pendingKey,
}: {
  recs: Recommendation[];
  limit?: number;
  compact?: boolean;
  onDo?: (rec: Recommendation) => void;
  onDisable?: (rec: Recommendation) => void;
  pendingKey?: string | null;
}) {
  const items = limit ? recs.slice(0, limit) : recs;
  return (
    <div className="space-y-2">
      {items.map((r, i) => (
        <RecommendationCard
          key={`${r.type}-${r.title}-${i}`}
          rec={r}
          compact={compact}
          onDo={onDo}
          onDisable={onDisable}
          pending={pendingKey === `${r.type}:${r.title}`}
        />
      ))}
    </div>
  );
}
