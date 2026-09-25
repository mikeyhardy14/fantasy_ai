import { clsx, type ClassValue } from "clsx";
import type { Flag, Priority, RosterSlot } from "./types";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function aiStatusLabel(enabled: boolean | undefined, provider: string | null | undefined): string {
  if (!enabled) return "Rule-based mode";
  if (provider === "gemini") return "Gemini connected";
  if (provider === "groq") return "Groq connected";
  return "OpenAI connected";
}

export function formatPoints(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "Never";
  const d = new Date(value);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export function relativeTime(value: string | null | undefined): string {
  if (!value) return "never";
  const diff = Date.now() - new Date(value).getTime();
  const minutes = Math.round(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export const POSITION_COLORS: Record<string, string> = {
  QB: "bg-rose-500/10 text-rose-300 ring-rose-500/25",
  RB: "bg-brand-soft text-brand ring-brand/20",
  WR: "bg-sky-500/10 text-sky-300 ring-sky-500/25",
  TE: "bg-amber-500/10 text-amber-300 ring-amber-500/25",
  K: "bg-[#3a3018] text-amber-200 ring-amber-400/30",
  DEF: "bg-surface-overlay text-slate-200 ring-surface-border",
  FLEX: "bg-teal-500/10 text-teal-300 ring-teal-500/25",
  SUPER_FLEX: "bg-[#3a3018] text-amber-200 ring-amber-400/30",
  BN: "bg-surface-overlay text-slate-400 ring-surface-border",
  IR: "bg-red-500/10 text-red-300 ring-red-500/25",
};

export function positionColor(position: string | null | undefined): string {
  return POSITION_COLORS[position ?? ""] ?? "bg-slate-600/20 text-slate-300 ring-slate-500/30";
}

export const PRIORITY_STYLES: Record<Priority, string> = {
  HIGH: "bg-red-500/15 text-red-300 ring-red-500/30",
  MEDIUM: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  LOW: "bg-slate-500/15 text-slate-300 ring-slate-500/30",
};

export const FLAG_LABELS: Record<Flag, { label: string; className: string }> = {
  BYE: { label: "BYE", className: "bg-slate-500/20 text-slate-200 ring-slate-400/30" },
  IR: { label: "IR", className: "bg-red-500/20 text-red-200 ring-red-500/40" },
  OUT: { label: "OUT", className: "bg-red-500/20 text-red-200 ring-red-500/40" },
  SUSPENDED: { label: "SUSP", className: "bg-red-500/20 text-red-200 ring-red-500/40" },
  DOUBTFUL: { label: "D", className: "bg-orange-500/20 text-orange-200 ring-orange-500/40" },
  QUESTIONABLE: { label: "Q", className: "bg-amber-500/20 text-amber-200 ring-amber-500/40" },
  INJURED: { label: "INJ", className: "bg-amber-500/20 text-amber-200 ring-amber-500/40" },
  INACTIVE: { label: "INACTIVE", className: "bg-slate-500/20 text-slate-300 ring-slate-500/40" },
  FREE_AGENT_NFL: { label: "FA", className: "bg-slate-500/20 text-slate-300 ring-slate-500/40" },
};

export const GRADE_STYLES: Record<string, string> = {
  Strong: "text-emerald-300",
  Adequate: "text-sky-300",
  "Needs depth": "text-amber-300",
  Weak: "text-red-300",
};

export function slotHasProblem(slot: RosterSlot): boolean {
  return slot.flags.some((f) => ["BYE", "IR", "OUT", "DOUBTFUL", "SUSPENDED"].includes(f));
}

export function slotNeedsAttention(slot: RosterSlot): boolean {
  return slot.flags.length > 0;
}

export const PROVIDER_LABELS: Record<string, string> = {
  sleeper: "Sleeper",
  yahoo: "Yahoo Fantasy",
  espn: "ESPN Fantasy",
  nfl: "NFL Fantasy",
  demo: "Demo",
};
