"use client";

import { ProposeTradeDialog } from "@/components/propose-trade";
import { NoLeague } from "@/components/no-league";
import { PageHeader } from "@/components/page-header";
import { RecommendationList } from "@/components/recommendation-card";
import { Badge, PositionBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { EmptyState, ErrorState, InlineError, SkeletonRows } from "@/components/ui/states";
import { api } from "@/lib/api";
import { useLeague } from "@/lib/league";
import { useLeagueDetail, usePlayers, useRecommendations, useTeam, useTrades } from "@/lib/queries";
import type { Player, TradeAnalysis, TradeReview, Transaction } from "@/lib/types";
import { cn, formatPoints } from "@/lib/utils";
import { useMutation } from "@tanstack/react-query";
import { ArrowLeftRight, X } from "lucide-react";
import { useMemo, useState } from "react";

export default function TradesPage() {
  const { selected, loading, leagues } = useLeague();
  if (loading) return <SkeletonRows rows={10} />;
  if (!leagues.length || !selected) return <NoLeague />;
  return <TradesView leagueId={selected.id} />;
}

const VERDICT_STYLE: Record<TradeAnalysis["verdict"], string> = {
  ACCEPT: "bg-emerald-500/15 text-emerald-200 ring-emerald-500/30",
  REJECT: "bg-red-500/15 text-red-200 ring-red-500/30",
  NEGOTIATE: "bg-amber-500/15 text-amber-200 ring-amber-500/30",
  UNCLEAR: "bg-slate-500/15 text-slate-200 ring-slate-500/30",
};

function TradesView({ leagueId }: { leagueId: string }) {
  const { selected } = useLeague();
  const detail = useLeagueDetail(leagueId);
  const team = useTeam(leagueId);
  const recs = useRecommendations(leagueId);
  const [search, setSearch] = useState("");
  const pool = usePlayers(leagueId, { search: search.length >= 2 ? search : undefined, available: false, limit: 30 });
  const [give, setGive] = useState<Player[]>([]);
  const [receive, setReceive] = useState<Player[]>([]);
  const [confirming, setConfirming] = useState(false);
  const [sent, setSent] = useState<string | null>(null);
  const writes = selected?.provider === "sleeper" && !!detail.data?.account.writes_enabled;
  const analyze = useMutation({ mutationFn: () => api.ai.trade(leagueId, { give: give.map((p) => p.id), receive: receive.map((p) => p.id) }) });
  const propose = useMutation({
    mutationFn: () => api.leagues.proposeTrade(leagueId, { give: give.map((player) => player.id), receive: receive.map((player) => player.id) }),
    onSuccess: (result) => {
      setConfirming(false);
      setSent(result.message);
      setGive([]);
      setReceive([]);
    },
  });

  const roster = useMemo(() => [...(team.data?.starters ?? []), ...(team.data?.bench ?? []), ...(team.data?.reserve ?? [])].map((s) => s.player!).filter(Boolean), [team.data]);
  const rosterIds = useMemo(() => new Set(roster.map((p) => p.id)), [roster]);
  const tradeRecs = (recs.data ?? []).filter((r) => r.type === "TRADE_TARGET" || r.type === "ROSTER_WEAKNESS");

  const toggle = (list: Player[], set: (v: Player[]) => void, p: Player) =>
    set(list.some((x) => x.id === p.id) ? list.filter((x) => x.id !== p.id) : list.length < 6 ? [...list, p] : list);

  return (
    <div className="space-y-6">
      <PageHeader title="Trades" description="Review trades that already went through, or send an offer. The other manager accepts it in Sleeper." />
      <MadeTrades leagueId={leagueId} />
      <div className="grid gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader title="You give" description="Pick from your roster" />
              <CardBody className="max-h-80 overflow-y-auto p-2">
                {team.isLoading ? <SkeletonRows rows={6} /> : roster.map((p) => <PickRow key={p.id} p={p} active={give.some((x) => x.id === p.id)} onClick={() => toggle(give, setGive, p)} />)}
              </CardBody>
            </Card>
            <Card>
              <CardHeader title="You receive" description="Search any rostered player in the league" />
              <CardBody className="space-y-2 p-2">
                <Input placeholder="Search players…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search trade targets" />
                <div className="max-h-64 overflow-y-auto">
                  {search.length < 2 ? (
                    <p className="p-3 text-xs text-slate-500">Type at least two characters.</p>
                  ) : pool.isLoading ? (
                    <SkeletonRows rows={4} />
                  ) : (
                    (pool.data ?? []).filter((p) => !rosterIds.has(p.id)).map((p) => <PickRow key={p.id} p={p} active={receive.some((x) => x.id === p.id)} onClick={() => toggle(receive, setReceive, p)} />)
                  )}
                  {search.length >= 2 && pool.data && !pool.data.filter((p) => !rosterIds.has(p.id)).length ? <p className="p-3 text-xs text-slate-500">No matches.</p> : null}
                </div>
              </CardBody>
            </Card>
          </div>

          <Card>
            <CardBody className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <Chips players={give} onRemove={(p) => setGive(give.filter((x) => x.id !== p.id))} empty="Select players to give" />
                <ArrowLeftRight className="h-4 w-4 text-slate-500" />
                <Chips players={receive} onRemove={(p) => setReceive(receive.filter((x) => x.id !== p.id))} empty="Select players to receive" />
              </div>
              <div className="flex flex-wrap gap-2">
                <Button onClick={() => analyze.mutate()} disabled={!give.length || !receive.length} loading={analyze.isPending}>Analyze trade</Button>
                {writes ? (
                  <Button
                    variant="secondary"
                    data-testid="propose-trade"
                    disabled={!give.length || !receive.length}
                    onClick={() => {
                      propose.reset();
                      setSent(null);
                      setConfirming(true);
                    }}
                  >
                    Propose trade
                  </Button>
                ) : null}
              </div>
            </CardBody>
            {detail.data && !writes ? (
              <p className="px-5 pb-4 text-xs text-slate-500">Save a Sleeper token in Settings to send an offer.</p>
            ) : null}
            {sent ? <p className="px-5 pb-4 text-sm text-emerald-200" data-testid="propose-result">{sent}</p> : null}
            <InlineError error={analyze.error} />
          </Card>
          {confirming ? (
            <ProposeTradeDialog
              give={give}
              receive={receive}
              pending={propose.isPending}
              error={propose.error instanceof Error ? propose.error.message : null}
              onSend={() => propose.mutate()}
              onCancel={() => {
                if (!propose.isPending) setConfirming(false);
              }}
            />
          ) : null}

          {analyze.data ? <TradeResult analysis={analyze.data.analysis} generatedBy={analyze.data.generated_by} /> : null}
        </div>
        <div className="space-y-6">
          <Card>
            <CardHeader title="Trade strategy" description="From your positional depth" />
            <CardBody>{recs.isLoading ? <SkeletonRows rows={3} /> : recs.error ? <ErrorState error={recs.error} className="py-4" /> : tradeRecs.length ? <RecommendationList recs={tradeRecs} /> : <EmptyState title="No trade angles flagged" description="Your roster is balanced across positions." className="py-6" />}</CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}

function MadeTrades({ leagueId }: { leagueId: string }) {
  const trades = useTrades(leagueId);
  const [reviews, setReviews] = useState<Record<string, TradeReview>>({});
  const review = useMutation({
    mutationFn: (id: string) => api.ai.reviewTrade(leagueId, id),
    onSuccess: (result, id) => setReviews((current) => ({ ...current, [id]: result })),
  });
  const rows = trades.data ?? [];
  return (
    <Card>
      <CardHeader title="Trades that were made" description="Scored from this week's projections. Asking the assistant to review trades uses the same record." />
      {trades.isLoading ? (
        <CardBody>
          <SkeletonRows rows={3} />
        </CardBody>
      ) : trades.error ? (
        <ErrorState error={trades.error} onRetry={() => trades.refetch()} />
      ) : rows.length ? (
        <CardBody className="space-y-4">
          {rows.map((trade) => (
            <div key={trade.id} className="border border-surface-border px-4 py-3" data-testid="made-trade">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm text-slate-100">
                  {trade.team_names.join(" ↔ ") || "Trade"}
                  <span className="ml-2 text-xs uppercase tracking-wide text-slate-500">
                    {trade.status}
                    {trade.week ? ` · Week ${trade.week}` : ""}
                    {trade.involves_user ? " · Your roster" : ""}
                  </span>
                </p>
                <Button
                  onClick={() => review.mutate(trade.id)}
                  loading={review.isPending && review.variables === trade.id}
                  disabled={review.isPending}
                >
                  Review
                </Button>
              </div>
              <ul className="mt-2 space-y-1 text-sm text-slate-300">
                {receivedLines(trade).map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
              {trade.picks?.length ? <p className="mt-2 text-xs text-slate-500">Picks: {trade.picks.join(", ")}</p> : null}
              {reviews[trade.id] ? (
                <div className="mt-3">
                  <TradeResult
                    analysis={reviews[trade.id].analysis}
                    generatedBy={reviews[trade.id].generated_by}
                    giveLabel={reviews[trade.id].involves_user ? "You sent" : `${reviews[trade.id].perspective} sent`}
                    receiveLabel={reviews[trade.id].involves_user ? "You received" : `${reviews[trade.id].perspective} received`}
                  />
                </div>
              ) : null}
            </div>
          ))}
          <InlineError error={review.error} />
        </CardBody>
      ) : (
        <EmptyState title="No completed trades" description="When a trade is recorded in the league, it shows up here for review." className="py-6" />
      )}
    </Card>
  );
}

function receivedLines(trade: Transaction): string[] {
  const byTeam = new Map<string, string[]>();
  for (const add of trade.adds) {
    const team = add.team_name ?? "Unknown team";
    const names = byTeam.get(team) ?? [];
    names.push(add.player_name ?? "Unknown");
    byTeam.set(team, names);
  }
  return [...byTeam.entries()].map(([team, names]) => `${team} received ${names.join(", ")}`);
}

function PickRow({ p, active, onClick }: { p: Player; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} className={cn("flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-sm transition hover:bg-surface-overlay", active && "bg-brand-soft/40 ring-1 ring-inset ring-emerald-500/40")}>
      <span className="flex items-center gap-2 min-w-0">
        <PositionBadge position={p.position} />
        <span className="truncate text-slate-100">{p.name}</span>
        <span className="text-xs text-slate-500">{p.nfl_team ?? "FA"}</span>
        {p.injury_status ? <Badge className="bg-amber-500/15 text-amber-200 ring-amber-500/30">{p.injury_status}</Badge> : null}
      </span>
      <span className="text-right text-xs tabular-nums text-slate-400">
        <span className="block" title="Points scored this season">{formatPoints(p.season_points)}</span>
        <span className="block text-[10px] text-slate-500">proj {formatPoints(p.projected_points)}</span>
      </span>
    </button>
  );
}

function Chips({ players, onRemove, empty }: { players: Player[]; onRemove: (p: Player) => void; empty: string }) {
  if (!players.length) return <span className="text-xs text-slate-500">{empty}</span>;
  return (
    <span className="flex flex-wrap gap-1">
      {players.map((p) => (
        <span key={p.id} className="inline-flex items-center gap-1 rounded-md bg-surface-overlay px-2 py-1 text-xs text-slate-100 ring-1 ring-inset ring-surface-border">
          {p.name}
          <button onClick={() => onRemove(p)} aria-label={`Remove ${p.name}`} className="text-slate-400 hover:text-slate-100"><X className="h-3 w-3" /></button>
        </span>
      ))}
    </span>
  );
}

function TradeResult({
  analysis,
  generatedBy,
  giveLabel = "You give",
  receiveLabel = "You receive",
}: {
  analysis: TradeAnalysis;
  generatedBy: string;
  giveLabel?: string;
  receiveLabel?: string;
}) {
  return (
    <Card data-testid="trade-result">
      <CardHeader
        title={<span className="flex items-center gap-2">Verdict <Badge className={VERDICT_STYLE[analysis.verdict]}>{analysis.verdict}</Badge></span>}
        action={<Badge className="bg-slate-500/15 text-slate-400 ring-slate-500/30">{generatedBy === "deterministic" ? "Rule-based" : "AI"}</Badge>}
      />
      <CardBody className="space-y-4">
        <p className="text-sm text-slate-200">{analysis.summary}</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <SideBox label={giveLabel} side={analysis.you_give} />
          <SideBox label={receiveLabel} side={analysis.you_receive} />
        </div>
        <Section title="Roster impact" items={analysis.roster_impact} />
        <Section title="Lineup impact" items={analysis.lineup_impact} />
        <Section title="Risks" items={analysis.risks} />
        {analysis.data_gaps.length ? <Section title="Data not available" items={analysis.data_gaps} muted /> : null}
      </CardBody>
    </Card>
  );
}

function SideBox({ label, side }: { label: string; side: TradeAnalysis["you_give"] }) {
  return (
    <div className="rounded-lg border border-surface-border bg-surface p-3">
      <p className="text-[11px] uppercase tracking-wide text-slate-500">{label}</p>
      <ul className="mt-1 space-y-1 text-sm text-slate-100">
        {side.players.map((p, i) => (
          <li key={i} className="flex items-center gap-2"><PositionBadge position={side.positions[i]} />{p}{side.injured.includes(p) ? <Badge className="bg-amber-500/15 text-amber-200 ring-amber-500/30">INJ</Badge> : null}</li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-slate-500">Projected: {formatPoints(side.projected_points)}</p>
    </div>
  );
}

function Section({ title, items, muted }: { title: string; items: string[]; muted?: boolean }) {
  return (
    <div>
      <p className="mb-1 text-[11px] uppercase tracking-wide text-slate-500">{title}</p>
      <ul className={cn("space-y-1 text-sm", muted ? "text-slate-500" : "text-slate-300")}>
        {items.map((i, k) => (
          <li key={k}>• {i}</li>
        ))}
      </ul>
    </div>
  );
}
