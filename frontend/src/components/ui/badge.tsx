import { cn, FLAG_LABELS, positionColor, PRIORITY_STYLES } from "@/lib/utils";
import type { Flag, Priority } from "@/lib/types";
import type { HTMLAttributes } from "react";

export function Badge({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ring-1 ring-inset",
        className,
      )}
      {...props}
    />
  );
}

export function PositionBadge({ position, className }: { position: string | null | undefined; className?: string }) {
  return (
    <Badge className={cn("min-w-[2.5rem] justify-center", positionColor(position), className)} data-testid="position-badge">
      {position ?? "—"}
    </Badge>
  );
}

export function SlotBadge({ slot }: { slot: string }) {
  return <Badge className={cn("min-w-[3rem] justify-center", positionColor(slot))}>{slot.replace("_", " ")}</Badge>;
}

export function FlagBadges({ flags, injury }: { flags: Flag[]; injury?: string | null }) {
  if (!flags.length) return null;
  return (
    <span className="inline-flex flex-wrap gap-1">
      {flags.map((f) => {
        const meta = FLAG_LABELS[f];
        return (
          <Badge key={f} className={meta.className} title={f === "BYE" ? "On bye this week" : injury ?? f}>
            {meta.label}
          </Badge>
        );
      })}
    </span>
  );
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  return <Badge className={PRIORITY_STYLES[priority]}>{priority}</Badge>;
}

export function StatusDot({ status }: { status: "idle" | "syncing" | "success" | "error" }) {
  const color = { idle: "bg-slate-400", syncing: "bg-amber-400", success: "bg-brand", error: "bg-red-400" }[status];
  return <span className={cn("inline-block h-2 w-2 rounded-full", color)} aria-label={`sync ${status}`} />;
}
