"use client";

import { useAuth } from "@/lib/auth";
import { useLeague } from "@/lib/league";
import { useTeam } from "@/lib/queries";
import { cn } from "@/lib/utils";
import {
  ArrowLeftRight,
  LayoutDashboard,
  LayoutGrid,
  List,
  LogOut,
  Menu,
  MessageSquare,
  Settings,
  Sparkles,
  UserRound,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Brand } from "@/components/shell/brand";
import { Select } from "@/components/ui/input";

const NAV: { label: string; items: { href: string; label: string; icon: LucideIcon }[] }[] = [
  {
    label: "This week",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/league", label: "League View", icon: LayoutGrid },
      { href: "/team", label: "My Team", icon: UserRound },
      { href: "/players", label: "Players", icon: List },
    ],
  },
  {
    label: "League",
    items: [
      { href: "/teams", label: "Teams", icon: Users },
      { href: "/trades", label: "Trades", icon: ArrowLeftRight },
      { href: "/messages", label: "Chat", icon: MessageSquare },
    ],
  },
  {
    label: "Tools",
    items: [
      { href: "/assistant", label: "Assistant", icon: Sparkles },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

function currentPage(pathname: string): string {
  for (const group of NAV) {
    const hit = group.items.find((item) => pathname === item.href || pathname.startsWith(`${item.href}/`));
    if (hit) return hit.label;
  }
  if (pathname.startsWith("/connect")) return "Connect";
  return "OMAHA";
}

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { leagues, selected, select } = useLeague();
  const team = useTeam(selected?.id);
  const [open, setOpen] = useState(false);

  const nav = (
    <nav className="min-h-0 flex-1 space-y-5 overflow-y-auto px-3 pb-4">
      {NAV.map((group) => (
        <div key={group.label}>
          <p className="mb-1 px-3 text-[11px] font-medium uppercase tracking-wide text-slate-500">{group.label}</p>
          <div className="space-y-0.5">
            {group.items.map(({ href, label, icon: Icon }) => {
              const active = pathname === href || pathname.startsWith(`${href}/`);
              return (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setOpen(false)}
                  className={cn(
                    "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/70",
                    active ? "bg-emerald-400/20 font-medium text-emerald-100 ring-1 ring-inset ring-emerald-300/50" : "text-slate-300 hover:bg-white/5 hover:text-slate-100",
                  )}
                  aria-current={active ? "page" : undefined}
                >
                  <Icon className={cn("h-4 w-4 shrink-0", active ? "text-emerald-100" : "text-slate-500")} aria-hidden />
                  {label}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );

  const leagueSwitcher = (
    <div className="px-3 pb-3">
      <p className="mb-1.5 px-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">League</p>
      {leagues.length ? (
        <Select className="w-full" value={selected?.id ?? ""} onChange={(e) => select(e.target.value)} aria-label="Select league">
          {leagues.map((l) => (
            <option key={l.id} value={l.id}>
              {l.name} · {l.season}
            </option>
          ))}
        </Select>
      ) : (
        <Link href="/connect/sleeper" className="block rounded-lg border border-dashed border-surface-border px-3 py-2 text-xs text-slate-400 hover:border-brand hover:text-slate-100">
          Connect a league
        </Link>
      )}
      {selected ? (
        <div className="mt-2 flex gap-2 px-0.5">
          <span className="rounded-md bg-white/5 px-2 py-1 text-xs text-slate-300">Week {selected.current_week}</span>
          <span className="rounded-md bg-white/5 px-2 py-1 text-xs tabular-nums text-slate-300">{team.data?.team.record ?? "—"}</span>
        </div>
      ) : null}
    </div>
  );

  const content = (
    <div className="flex h-full min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between px-5 py-5">
        <Link href="/dashboard" className="text-slate-100" aria-label="OMAHA">
          <Brand />
        </Link>
        <button className="rounded-md p-1 text-slate-400 hover:text-slate-100 lg:hidden" onClick={() => setOpen(false)} aria-label="Close menu">
          <X className="h-5 w-5" />
        </button>
      </div>
      {leagueSwitcher}
      {nav}
      <div className="border-t border-white/10 p-3">
        <div className="flex items-center gap-2 rounded-lg px-1.5 py-1">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-soft text-xs font-medium text-emerald-200">
            {(user?.name ?? "?").slice(0, 1).toUpperCase()}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-slate-100">{user?.name}</p>
            <p className="truncate text-[11px] text-slate-500">{user?.email}</p>
          </div>
          <button onClick={logout} className="rounded-md p-2 text-slate-400 hover:bg-white/5 hover:text-slate-100" aria-label="Sign out" title="Sign out">
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      <header className="sticky top-0 z-30 flex items-center justify-between gap-3 border-b border-white/10 bg-surface/80 px-4 py-2.5 backdrop-blur-md lg:hidden">
        <button onClick={() => setOpen(true)} className="rounded-md p-1 text-slate-300" aria-label="Open menu">
          <Menu className="h-5 w-5" />
        </button>
        <div className="min-w-0 text-center">
          <p className="truncate font-serif text-base leading-tight text-slate-100">{currentPage(pathname)}</p>
          {selected ? <p className="truncate text-[10px] text-slate-500">{selected.name}</p> : null}
        </div>
        <span className="w-7" />
      </header>
      <div
        className={cn(
          "fixed inset-0 z-40 bg-[#1c1916]/40 transition-opacity duration-300 lg:hidden",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={() => setOpen(false)}
      />
      <aside
        className={cn(
          "z-50 flex w-64 shrink-0 flex-col border-r border-white/10 bg-surface-raised/95 backdrop-blur-md max-lg:fixed max-lg:inset-y-0 max-lg:left-0 max-lg:shadow-xl max-lg:transition-transform max-lg:duration-300 max-lg:ease-[cubic-bezier(0.22,1,0.36,1)] lg:sticky lg:top-0 lg:h-screen",
          open ? "max-lg:translate-x-0" : "max-lg:-translate-x-full",
        )}
      >
        {content}
      </aside>
    </>
  );
}
