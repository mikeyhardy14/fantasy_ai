"use client";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { EmptyState, ErrorState, InlineError, SkeletonRows } from "@/components/ui/states";
import { api, ApiError } from "@/lib/api";
import { useLeague } from "@/lib/league";
import type { FantasyAccount, ProviderLeague } from "@/lib/types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

export default function ConnectSleeperPage() {
  const [username, setUsername] = useState("");
  const [account, setAccount] = useState<FantasyAccount | null>(null);
  const [season, setSeason] = useState<number | undefined>(undefined);
  const qc = useQueryClient();
  const { refetch: refetchLeagues, select } = useLeague();
  const router = useRouter();

  const existing = useQuery({ queryKey: ["accounts"], queryFn: api.integrations.accounts });
  const sleeperAccount = account ?? existing.data?.find((a) => a.provider === "sleeper") ?? null;

  const connect = useMutation({
    mutationFn: (u: string) => api.integrations.connectSleeper(u),
    onSuccess: (acc) => {
      setAccount(acc);
      void qc.invalidateQueries({ queryKey: ["accounts"] });
    },
  });

  const leagues = useQuery({
    queryKey: ["sleeper-leagues", sleeperAccount?.id, season],
    queryFn: () => api.integrations.sleeperLeagues(season),
    enabled: !!sleeperAccount,
    retry: false,
  });

  const importLeague = useMutation({
    mutationFn: (externalId: string) => api.integrations.importSleeperLeague(externalId),
    onSuccess: (league) => {
      void qc.invalidateQueries({ queryKey: ["sleeper-leagues"] });
      refetchLeagues();
      select(league.id);
      router.push("/dashboard");
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    connect.mutate(username.trim());
  }

  const thisYear = new Date().getFullYear();
  const seasons = [thisYear + 1, thisYear, thisYear - 1, thisYear - 2].filter((y) => y >= 2017);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader title="Connect Sleeper" description="Import uses your Sleeper username. Lineup edits use a separate token, saved later in Settings." />

      <Card>
        <CardHeader
          title={<span className="flex items-center gap-2"><StepNumber n={1} done={!!sleeperAccount} /> Sleeper username</span>}
          description={sleeperAccount ? `Connected as @${sleeperAccount.username}` : "Enter the username you sign in to Sleeper with"}
        />
        <CardBody>
          <form onSubmit={onSubmit} className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <Label htmlFor="username">Username</Label>
              <Input id="username" value={username} onChange={(e) => setUsername(e.target.value)} placeholder={sleeperAccount?.username ?? "e.g. fantasyking"} pattern="[A-Za-z0-9_.\-]+" maxLength={64} required />
            </div>
            <Button type="submit" loading={connect.isPending}>{sleeperAccount ? "Switch account" : "Connect"}</Button>
          </form>
          <div className="mt-3"><InlineError error={connect.error} /></div>
          <p className="mt-3 text-xs text-slate-500">No Sleeper password is stored. A lineup change only happens after you paste the token in Settings.</p>
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title={<span className="flex items-center gap-2"><StepNumber n={2} done={false} /> Choose a league to import</span>}
          description={leagues.data ? `${leagues.data.leagues.length} league${leagues.data.leagues.length === 1 ? "" : "s"} for the ${leagues.data.season} season` : "Your NFL leagues will appear here"}
          action={
            sleeperAccount ? (
              <Select value={season ?? ""} onChange={(e) => setSeason(e.target.value ? Number(e.target.value) : undefined)} aria-label="Season">
                <option value="">Current season</option>
                {seasons.map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </Select>
            ) : null
          }
        />
        <CardBody className="p-0">
          {!sleeperAccount ? (
            <EmptyState title="Connect your account first" className="py-8" />
          ) : leagues.isLoading ? (
            <div className="p-5"><SkeletonRows rows={3} /></div>
          ) : leagues.error ? (
            <ErrorState error={leagues.error} onRetry={() => leagues.refetch()} title={leagues.error instanceof ApiError && leagues.error.status === 429 ? "Sleeper is rate limiting" : "Could not load leagues"} />
          ) : !leagues.data?.leagues.length ? (
            <EmptyState title="No leagues found" description={`@${sleeperAccount.username} has no NFL leagues for ${leagues.data?.season}. Try a different season.`} className="py-8" />
          ) : (
            <ul className="divide-y divide-surface-border/60">
              {leagues.data.leagues.map((lg) => (
                <LeagueRow key={lg.external_league_id} league={lg} importing={importLeague.isPending && importLeague.variables === lg.external_league_id} disabled={importLeague.isPending} onImport={() => importLeague.mutate(lg.external_league_id)} />
              ))}
            </ul>
          )}
          {importLeague.error ? <div className="p-4"><InlineError error={importLeague.error} /></div> : null}
        </CardBody>
      </Card>
    </div>
  );
}

function StepNumber({ n, done }: { n: number; done: boolean }) {
  return (
    <span className={`flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-semibold ${done ? "bg-brand text-slate-950" : "bg-surface-overlay text-slate-300"}`}>
      {done ? <Check className="h-3 w-3" /> : n}
    </span>
  );
}

function LeagueRow({ league, onImport, importing, disabled }: { league: ProviderLeague; onImport: () => void; importing: boolean; disabled: boolean }) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 px-5 py-3" data-testid="provider-league">
      <div>
        <p className="font-medium text-slate-100">{league.name}</p>
        <p className="text-xs text-slate-500">{league.season} · {league.team_count} teams · {league.scoring_type ?? "custom"} · {league.status?.replace("_", " ") ?? ""}</p>
      </div>
      <div className="flex items-center gap-2">
        {league.imported ? (
          <Badge className="bg-brand-soft text-emerald-200 ring-emerald-500/30">Live</Badge>
        ) : (
          <Button size="sm" onClick={onImport} loading={importing} disabled={disabled}>
            Import
          </Button>
        )}
      </div>
    </li>
  );
}
