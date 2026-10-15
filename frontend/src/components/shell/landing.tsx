"use client";

import { Brand } from "@/components/shell/brand";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

const steps = [
  {
    title: "Import a league",
    body: "Connect Sleeper with a username. Your account here holds imported leagues — it is not your Sleeper login.",
  },
  {
    title: "See the week in one place",
    body: "Rosters, matchups, waivers, and standings stay tied to the league data you imported.",
  },
  {
    title: "Ask from real data",
    body: "The assistant answers with tool calls against your league — not generic fantasy chatter.",
  },
] as const;

export function LandingHome() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [loading, user, router]);

  if (loading || user) {
    return (
      <div className="flex min-h-screen items-center justify-center px-6">
        <Brand className="opacity-70" />
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <header className="landing-nav absolute inset-x-0 top-0 z-20 flex items-center justify-between px-6 py-5 sm:px-10">
        <Brand mark="h-7 w-7" className="text-slate-100" />
        <Link
          href="/login"
          className="text-sm font-medium text-slate-300 transition hover:text-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
        >
          Sign in
        </Link>
      </header>

      <section className="relative isolate flex min-h-screen flex-col justify-end overflow-hidden px-6 pb-16 pt-28 sm:px-10 sm:pb-20 lg:justify-center lg:pb-24 lg:pt-24">
        <LandingHeroVisual />
        <div className="relative z-10 max-w-xl landing-hero-copy">
          <p className="font-serif text-5xl leading-none tracking-wide text-slate-100 sm:text-6xl lg:text-7xl">OMAHA</p>
          <h1 className="mt-6 max-w-lg text-3xl leading-tight text-slate-100 sm:text-4xl">
            Rosters, matchups, and waivers for the leagues you import.
          </h1>
          <p className="mt-4 max-w-md text-base leading-relaxed text-slate-300">
            An AI fantasy desk that reads your real league data — starting with Sleeper.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link href="/register">
              <Button size="lg">Create an account</Button>
            </Link>
            <Link href="/login">
              <Button size="lg" variant="secondary">
                Sign in
              </Button>
            </Link>
          </div>
          <div className="landing-desk mt-12 border border-surface-border/80 bg-surface-raised/80 p-4 backdrop-blur-sm lg:hidden">
            <div className="flex items-end justify-between gap-6">
              <div>
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Your score</p>
                <p className="mt-1 font-serif text-4xl text-slate-100">98.4</p>
              </div>
              <div className="text-right">
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Opponent</p>
                <p className="mt-1 font-serif text-3xl text-slate-300">86.1</p>
              </div>
            </div>
            <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-surface-overlay">
              <div className="landing-bar h-full w-[72%] rounded-full bg-brand" />
            </div>
          </div>
        </div>
      </section>

      <section className="border-t border-surface-border px-6 py-20 sm:px-10">
        <div className="mx-auto max-w-3xl">
          <h2 className="text-3xl text-slate-100 sm:text-4xl">How it works</h2>
          <p className="mt-3 max-w-xl text-sm leading-relaxed text-slate-400">
            Three steps from a blank account to a live league desk.
          </p>
          <ol className="mt-12 space-y-10">
            {steps.map((step, index) => (
              <li key={step.title} className="grid gap-2 sm:grid-cols-[3rem_1fr] sm:gap-6">
                <span className="font-serif text-3xl text-amber-400/90" aria-hidden>
                  {index + 1}
                </span>
                <div>
                  <h3 className="text-lg font-medium text-slate-100">{step.title}</h3>
                  <p className="mt-2 max-w-prose text-sm leading-relaxed text-slate-400">{step.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="border-t border-surface-border bg-surface-raised/60 px-6 py-20 sm:px-10">
        <div className="mx-auto max-w-3xl">
          <h2 className="text-3xl text-slate-100 sm:text-4xl">Built for imported leagues</h2>
          <p className="mt-3 max-w-xl text-sm leading-relaxed text-slate-400">
            OMAHA normalizes your league into one model, then keeps lineups, matchups, and advice grounded in that data.
          </p>
          <div className="mt-10 flex flex-wrap gap-3">
            <Link href="/register">
              <Button size="lg">Get started</Button>
            </Link>
            <Link href="/login">
              <Button size="lg" variant="ghost">
                I already have an account
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-surface-border px-6 py-8 sm:px-10">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-4 text-sm text-slate-500">
          <Brand mark="h-6 w-6" className="text-slate-400" />
          <p>Fantasy football from your league data.</p>
        </div>
      </footer>
    </div>
  );
}

function LandingHeroVisual() {
  return (
    <div className="pointer-events-none absolute inset-0 -z-0" aria-hidden>
      <div className="landing-field absolute inset-0" />
      <div className="absolute inset-y-0 right-0 hidden w-[58%] lg:block">
        <div className="landing-desk absolute inset-6 overflow-hidden rounded-2xl border border-surface-border/80 bg-surface-raised/75 shadow-xl backdrop-blur-sm">
          <div className="flex items-center justify-between border-b border-surface-border px-5 py-3">
            <span className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">Week 7 · Live desk</span>
            <span className="rounded bg-brand/20 px-2 py-0.5 text-[11px] font-medium text-emerald-300">Synced</span>
          </div>
          <div className="grid h-[calc(100%-2.75rem)] grid-cols-[1.1fr_0.9fr] gap-px bg-surface-border/60">
            <div className="bg-surface-raised p-5">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Your lineup</p>
              <ul className="mt-4 space-y-3">
                {[
                  ["QB", "Mahomes", "18.4"],
                  ["RB", "Bijan", "14.1"],
                  ["WR", "Chase", "16.8"],
                  ["FLEX", "Kyren", "12.2"],
                ].map(([slot, name, pts]) => (
                  <li key={slot} className="flex items-center justify-between border-b border-surface-border/70 pb-2 text-sm last:border-0">
                    <span className="w-10 text-xs text-slate-500">{slot}</span>
                    <span className="flex-1 text-slate-200">{name}</span>
                    <span className="font-medium text-amber-300">{pts}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="bg-surface p-5">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Matchup</p>
              <div className="mt-6 space-y-6">
                <div>
                  <div className="flex items-end justify-between">
                    <span className="text-slate-200">You</span>
                    <span className="font-serif text-4xl text-slate-100">98.4</span>
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-overlay">
                    <div className="landing-bar h-full w-[72%] rounded-full bg-brand" />
                  </div>
                </div>
                <div>
                  <div className="flex items-end justify-between">
                    <span className="text-slate-400">Opponent</span>
                    <span className="font-serif text-4xl text-slate-300">86.1</span>
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-overlay">
                    <div className="landing-bar-delay h-full w-[61%] rounded-full bg-amber-400/80" />
                  </div>
                </div>
              </div>
              <p className="mt-8 text-xs leading-relaxed text-slate-500">
                Projections and live scoring stay bound to the roster you imported.
              </p>
            </div>
          </div>
        </div>
      </div>
      <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-surface to-transparent lg:hidden" />
    </div>
  );
}
