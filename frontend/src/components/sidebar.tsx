"use client";

import { useAuth } from "@/lib/auth";
import { useLeague } from "@/lib/league";
import { cn, PROVIDER_LABELS } from "@/lib/utils";
import { LogOut, Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { StatusDot } from "./ui/badge";
import { Select } from "./ui/input";

export const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/multibox", label: "Multi-Box" },
  { href: "/team", label: "My Team" },
  { href: "/matchup", label: "Matchup" },
  { href: "/players", label: "Players" },
  { href: "/rankings", label: "Rankings" },
  { href: "/waivers", label: "Waivers" },
  { href: "/trades", label: "Trades" },
  { href: "/assistant", label: "Assistant" },
  { href: "/settings", label: "Settings" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { leagues, selected, select } = useLeague();
  const [open, setOpen] = useState(false);

  const nav = (
    <nav className="flex-1 space-y-0.5 px-3">
      {NAV.map(({ href, label }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            onClick={() => setOpen(false)}
            className={cn(
              "block border-l-2 px-3 py-1.5 text-sm transition",
              active ? "border-brand font-medium text-slate-100" : "border-transparent text-slate-400 hover:text-slate-100",
            )}
            aria-current={active ? "page" : undefined}
          >
            {label}
          </Link>
        );
      })}
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
        <Link href="/connect/sleeper" className="block border border-dashed border-surface-border px-3 py-2 text-xs text-slate-400 hover:border-brand hover:text-slate-100">
          Connect a league
        </Link>
      )}
      {selected ? (
        <div className="mt-2 flex items-center justify-between gap-2 px-1 text-[11px] text-slate-500">
          <span className="flex items-center gap-2">
            <StatusDot status={selected.sync_status} />
            {PROVIDER_LABELS[selected.provider] ?? selected.provider} · Week {selected.current_week}
          </span>
          <Link href="/multibox" className="shrink-0 text-brand hover:underline">
            All teams
          </Link>
        </div>
      ) : null}
    </div>
  );

  const content = (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-5 py-5">
        <Link href="/dashboard" className="text-slate-100">
          <span className="font-serif text-2xl leading-none">Fantasy</span>
        </Link>
        <button className="rounded-md p-1 text-slate-400 hover:text-slate-100 lg:hidden" onClick={() => setOpen(false)} aria-label="Close menu">
          <X className="h-5 w-5" />
        </button>
      </div>
      {leagueSwitcher}
      {nav}
      <div className="border-t border-surface-border p-3">
        <div className="flex items-center justify-between gap-2 px-2">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-slate-100">{user?.name}</p>
            <p className="truncate text-[11px] text-slate-500">{user?.email}</p>
          </div>
          <button onClick={logout} className="rounded-md p-2 text-slate-400 hover:bg-surface-overlay hover:text-slate-100" aria-label="Sign out" title="Sign out">
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-surface-border bg-surface/90 px-4 py-3 backdrop-blur lg:hidden">
        <button onClick={() => setOpen(true)} className="rounded-md p-1 text-slate-300" aria-label="Open menu">
          <Menu className="h-5 w-5" />
        </button>
        <span className="font-serif text-lg text-slate-100">{selected?.name ?? "Fantasy"}</span>
        <span className="w-7" />
      </header>
      {open ? <div className="fixed inset-0 z-40 bg-[#1c1916]/40 lg:hidden" onClick={() => setOpen(false)} /> : null}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 border-r border-surface-border bg-surface-raised transition-transform lg:static lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        {content}
      </aside>
    </>
  );
}
