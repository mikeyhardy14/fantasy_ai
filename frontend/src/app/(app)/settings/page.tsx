"use client";

import { PageHeader } from "@/components/page-header";
import { Badge, StatusDot } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { EmptyState, InlineError, SkeletonRows } from "@/components/ui/states";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useLeague } from "@/lib/league";
import { readLineupAutoApprove, writeLineupAutoApprove } from "@/lib/lineup-approval";
import { useHealth } from "@/lib/queries";
import { aiStatusLabel, formatDate, PROVIDER_LABELS } from "@/lib/utils";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function SettingsPage() {
  const { user } = useAuth();
  const { leagues, refetch, select } = useLeague();
  const router = useRouter();
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: api.integrations.accounts });
  const providers = useQuery({ queryKey: ["providers"], queryFn: api.integrations.providers });
  const health = useHealth();
  const demo = useMutation({
    mutationFn: api.demo.createLeague,
    onSuccess: (league) => {
      refetch();
      select(league.id);
      router.push("/dashboard");
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" description="Account, connected platforms and server status." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Account" />
          <CardBody className="text-sm">
            <dl className="space-y-2">
              <Row label="Name" value={user?.name} />
              <Row label="Email" value={user?.email} />
              <Row label="Member since" value={formatDate(user?.created_at)} />
            </dl>
          </CardBody>
        </Card>

        <AssistantApproval />

        <Card>
          <CardHeader title="Server" />
          <CardBody className="text-sm">
            {health.isLoading ? (
              <SkeletonRows rows={3} />
            ) : health.error ? (
              <InlineError error={health.error} />
            ) : (
              <dl className="space-y-2">
                <Row label="AI" value={<Badge className={health.data?.ai_enabled ? "bg-brand-soft text-emerald-200 ring-emerald-500/30" : "bg-amber-500/15 text-amber-200 ring-amber-500/30"}>{health.data?.ai_enabled ? aiStatusLabel(true, health.data.ai_provider) : "Rule-based fallback (set GEMINI_API_KEY)"}</Badge>} />
                <Row label="NFL data source" value={health.data?.nfl_data_provider} />
                <Row label="Environment" value={health.data?.environment} />
              </dl>
            )}
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader
            title="Connected fantasy accounts"
            action={
              <div className="flex gap-2">
                <Link href="/connect/sleeper"><Button size="sm"><Link2 className="h-3.5 w-3.5" /> Connect Sleeper</Button></Link>
                {health.data?.demo_enabled !== false ? <Button size="sm" variant="secondary" onClick={() => demo.mutate()} loading={demo.isPending}>Demo league</Button> : null}
              </div>
            }
          />
          <CardBody>
            <InlineError error={demo.error} />
            {accounts.isLoading ? (
              <SkeletonRows rows={2} />
            ) : accounts.data?.length ? (
              <ul className="divide-y divide-surface-border/60">
                {accounts.data.map((a) => (
                  <li key={a.id} className="py-3 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="font-medium text-slate-100">{PROVIDER_LABELS[a.provider] ?? a.provider} · @{a.username}</p>
                        <p className="text-xs text-slate-500">Last synced {formatDate(a.last_synced_at)} · {leagues.filter((l) => l.provider === a.provider).length} league(s) imported</p>
                      </div>
                      <div className="flex items-center gap-3">
                        {a.provider === "sleeper" ? (
                          <Badge className={a.writes_enabled ? "bg-brand-soft text-emerald-200 ring-emerald-500/30" : "bg-amber-500/15 text-amber-200 ring-amber-500/30"}>
                            {a.writes_enabled ? "Lineup edits on" : "Read only"}
                          </Badge>
                        ) : null}
                        {a.provider === "sleeper" ? <Link href="/connect/sleeper" className="text-xs text-emerald-300 hover:underline">Import more leagues</Link> : null}
                      </div>
                    </div>
                    {a.provider === "sleeper" ? <SleeperTokenForm accountId={a.id} enabled={a.writes_enabled} /> : null}
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="No accounts connected" description="Connect Sleeper to import your real leagues." className="py-6" />
            )}
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Imported leagues" />
          <CardBody className="p-0">
            {leagues.length ? (
              <ul className="divide-y divide-surface-border/60">
                {leagues.map((l) => (
                  <li key={l.id} className="flex flex-wrap items-center justify-between gap-2 px-5 py-3 text-sm">
                    <div className="flex items-center gap-3">
                      <StatusDot status={l.sync_status} />
                      <div>
                        <p className="font-medium text-slate-100">{l.name}</p>
                        <p className="text-xs text-slate-500">{PROVIDER_LABELS[l.provider] ?? l.provider} · {l.season} · {l.team_count} teams · {l.scoring_type ?? "custom"} · synced {formatDate(l.last_synced_at)}</p>
                        {l.sync_error ? <p className="text-xs text-red-300">{l.sync_error}</p> : null}
                      </div>
                    </div>
                    <Button size="sm" variant="ghost" onClick={() => { select(l.id); router.push("/dashboard"); }}>Open</Button>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="No leagues imported" className="py-6" />
            )}
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Supported platforms" description="Additional providers plug into the same FantasyProvider interface." />
          <CardBody>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {(providers.data ?? []).map((p) => (
                <div key={p.provider} className="rounded-lg border border-surface-border bg-surface p-3">
                  <p className="text-sm font-medium text-slate-100">{PROVIDER_LABELS[p.provider] ?? p.provider}</p>
                  <p className="text-xs text-slate-500">Auth: {p.capabilities.auth_type}</p>
                  <Badge className={p.implemented ? "mt-2 bg-brand-soft text-emerald-200 ring-emerald-500/30" : "mt-2 bg-slate-500/15 text-slate-400 ring-slate-500/30"}>{p.implemented ? "Available" : "Coming soon"}</Badge>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function AssistantApproval() {
  const [on, setOn] = useState(false);
  useEffect(() => setOn(readLineupAutoApprove()), []);
  return (
    <Card>
      <CardHeader title="Assistant" description="When the assistant says to start one player over another." />
      <CardBody>
        <label className="flex items-start gap-3 text-sm">
          <input
            type="checkbox"
            className="mt-1"
            checked={on}
            onChange={(event) => {
              writeLineupAutoApprove(event.target.checked);
              setOn(event.target.checked);
            }}
          />
          <span>
            <span className="font-medium text-slate-100">Auto-approve lineup moves</span>
            <span className="mt-1 block text-xs leading-relaxed text-slate-400">
              A recommended start-over is written to this week&apos;s lineup as soon as the assistant proposes it. Leave this off and the chat shows the move for you to approve.
            </span>
          </span>
        </label>
      </CardBody>
    </Card>
  );
}

function SleeperTokenForm({ accountId, enabled }: { accountId: string; enabled: boolean }) {
  const [token, setToken] = useState("");
  const qc = useQueryClient();
  const save = useMutation({
    mutationFn: () => api.integrations.saveSleeperToken(token.trim(), accountId),
    onSuccess: async () => {
      setToken("");
      await qc.invalidateQueries({ queryKey: ["accounts"] });
      await qc.invalidateQueries({ queryKey: ["leagues"] });
    },
  });
  const clear = useMutation({
    mutationFn: () => api.integrations.clearSleeperToken(accountId),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["accounts"] });
      await qc.invalidateQueries({ queryKey: ["leagues"] });
    },
  });

  return (
    <div className="mt-3 max-w-2xl space-y-2">
      <p className="text-xs leading-relaxed text-slate-400">
        {enabled
          ? "A Sleeper token is saved for this account. Lineups you edit are written with it."
          : "To edit a lineup, paste the token from the Sleeper web app: DevTools, Application, Local Storage, sleeper.com, key token."}{" "}
        It grants full access to your Sleeper account, lasts about a year, and is stored encrypted on the server. It is never sent back to this browser.
      </p>
      <div className="flex flex-wrap gap-2">
        <Input
          type="password"
          autoComplete="off"
          spellCheck={false}
          placeholder="eyJ..."
          value={token}
          onChange={(event) => setToken(event.target.value)}
          className="max-w-md"
          aria-label="Sleeper token"
        />
        <Button size="sm" onClick={() => save.mutate()} loading={save.isPending} disabled={token.trim().length < 20}>
          Save token
        </Button>
        {enabled ? (
          <Button size="sm" variant="secondary" onClick={() => clear.mutate()} loading={clear.isPending}>
            Remove token
          </Button>
        ) : null}
      </div>
      <InlineError error={save.error || clear.error} />
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-surface-border/40 pb-2">
      <dt className="text-slate-400">{label}</dt>
      <dd className="text-right text-slate-100">{value ?? "—"}</dd>
    </div>
  );
}
