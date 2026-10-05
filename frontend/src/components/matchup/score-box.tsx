"use client";

import { LivePoints } from "@/components/shell/live-points";
import { leagueInitials, safeImageUrl } from "@/lib/league-location";
import { cn } from "@/lib/utils";
import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";
import { useState } from "react";

type ScoreBoxShared = {
  live?: boolean;
  highlight?: boolean;
  status?: ReactNode;
  clock?: ReactNode;
  footer?: ReactNode;
  compact?: boolean;
  children: ReactNode;
};

export function ScoreBox({
  as = "button",
  live,
  highlight,
  status,
  clock,
  footer,
  compact,
  className,
  children,
  ...props
}: ScoreBoxShared &
  (
    | ({ as?: "button" } & ButtonHTMLAttributes<HTMLButtonElement>)
    | ({ as: "div" } & HTMLAttributes<HTMLDivElement>)
  )) {
  const cls = cn(
    "flex w-full flex-col rounded-lg border text-left text-slate-100 shadow-sm",
    compact ? "gap-0.5 px-2 py-1.5" : "gap-1.5 px-3 py-2.5",
    as === "button" && "transition hover:bg-white/[0.04] disabled:cursor-default disabled:hover:bg-inherit",
    live && "border-red-400/50 bg-red-500/10",
    highlight && !live && "border-emerald-400/40 bg-emerald-400/10",
    !live && !highlight && "border-white/10 bg-black/25",
    className,
  );
  const body = (
    <>
      {status || clock ? (
        <div className="flex items-center justify-between gap-2">
          {status ? (
            <span className={cn("inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide", live ? "text-red-300" : "text-slate-500")}>
              {live ? <span className="h-1.5 w-1.5 rounded-full bg-red-400" aria-hidden /> : null}
              {status}
            </span>
          ) : (
            <span />
          )}
          {clock ? <span className="shrink-0 text-[10px] tabular-nums text-slate-400">{clock}</span> : null}
        </div>
      ) : null}
      <div className="space-y-0.5">{children}</div>
      {footer ? <div className={cn(compact ? "pt-0.5" : "border-t border-white/10 pt-1.5")}>{footer}</div> : null}
    </>
  );
  if (as === "div") {
    return (
      <div className={cls} {...(props as HTMLAttributes<HTMLDivElement>)}>
        {body}
      </div>
    );
  }
  return (
    <button type="button" className={cls} {...(props as ButtonHTMLAttributes<HTMLButtonElement>)}>
      {body}
    </button>
  );
}

export function ScoreBoxSide({
  mark,
  name,
  score,
  detail,
  ahead,
}: {
  mark?: ReactNode;
  name: ReactNode;
  score: string;
  detail?: ReactNode;
  ahead?: boolean;
}) {
  return (
    <div
      className={cn("flex items-center gap-2 rounded-md", ahead && "-mx-1 bg-white/15 px-1 py-0.5")}
      data-testid="score-row"
      data-ahead={ahead ? "true" : "false"}
    >
      {mark}
      <span className="min-w-0 flex-1">
        <span className={cn("block truncate text-xs", ahead ? "font-semibold text-white" : "text-slate-300")}>{name}</span>
        {detail ? <span className="block truncate text-[10px] text-slate-400">{detail}</span> : null}
      </span>
      <LivePoints
        value={score}
        className={cn("shrink-0 font-serif tabular-nums leading-none", ahead ? "text-xl text-white" : "text-lg text-slate-300")}
      />
    </div>
  );
}

export function ScoreMark({
  src,
  label,
  alt,
  ring,
  size = "sm",
  priority = false,
}: {
  src?: string | null;
  label: string;
  alt?: string;
  ring?: boolean;
  size?: "sm" | "md";
  priority?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  const url = failed ? null : safeImageUrl(src);
  const px = size === "md" ? 28 : 24;
  const box = size === "md" ? "h-7 w-7 text-[9px]" : "h-6 w-6 text-[8px]";
  const fallback = label.length <= 4 ? label : leagueInitials(label);
  const frame = cn(
    "inline-flex shrink-0 items-center justify-center rounded-full bg-white text-slate-800",
    box,
    ring && "ring-2 ring-emerald-300",
  );
  if (!url) {
    return (
      <span className={cn(frame, "font-semibold")} aria-hidden>
        {fallback}
      </span>
    );
  }
  return (
    <img
      src={url}
      alt={alt ?? ""}
      width={px}
      height={px}
      fetchPriority={priority ? "high" : undefined}
      loading={priority ? "eager" : "lazy"}
      decoding="async"
      className={cn(frame, "object-contain p-0.5")}
      onError={() => setFailed(true)}
    />
  );
}
