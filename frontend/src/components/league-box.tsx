"use client";

import { opponentLabel, PlayerFace, seasonTitle } from "@/components/player-face";
import { PlayerName } from "@/components/player-sheet";
import { PositionBadge } from "@/components/ui/badge";
import { leagueInitials, leagueLocation, safeImageUrl } from "@/lib/league-location";
import type { League, Matchup, Team } from "@/lib/types";
import { cn, formatPoints, slotHasProblem } from "@/lib/utils";
import { ExternalLink } from "lucide-react";
import Link from "next/link";

const PLATFORM_STYLES: Record<string, string> = {
  sleeper: "bg-slate-100 text-slate-950",
  yahoo: "bg-slate-100 text-slate-950",
  espn: "bg-slate-100 text-slate-950",
  nfl: "bg-slate-100 text-slate-950",
  demo: "bg-slate-100 text-slate-950",
};

export function PlatformMark({ provider, label }: { provider: string; label: string }) {
  const letter = label.replace(/[^A-Za-z]/g, "").slice(0, 1).toUpperCase() || "?";
  return (
    <span
      data-testid="platform-icon"
      title={`Hosted on ${label}`}
      className={cn(
        "inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-md text-[11px] font-bold",
        PLATFORM_STYLES[provider] ?? "bg-slate-600 text-white",
      )}
      aria-hidden
    >
      {letter}
    </span>
  );
}

export function LeagueAvatar({ name, avatar }: { name: string; avatar: string | null }) {
  const src = safeImageUrl(avatar);
  if (src) {
    return <img src={src} alt="" data-testid="league-avatar" className="h-10 w-10 object-cover ring-1 ring-surface-border" />;
  }
  return (
    <span
      data-testid="league-avatar"
      className="inline-flex h-10 w-10 items-center justify-center bg-surface-overlay font-serif text-sm text-slate-100 ring-1 ring-surface-border"
      aria-hidden
    >
      {leagueInitials(name)}
    </span>
  );
}

export function LeagueBox({
  league,
  team,
  matchup,
  loading,
  error,
  onSelect,
}: {
  league: League;
  team?: Team;
  matchup?: Matchup | null;
  loading: boolean;
  error: Error | null;
  onSelect: () => void;
}) {
  const location = leagueLocation(league);
  const issues = team?.lineup_issues.length ?? 0;
  const live = matchup?.status === "in_progress";

  return (
    <article
      data-testid="league-box"
      className={cn(
        "flex flex-col overflow-hidden border border-surface-border bg-surface-raised",
        issues && "border-l-2 border-l-red-400",
      )}
    >
      <header className="flex items-start gap-3 border-b border-surface-border px-4 py-3">
        <LeagueAvatar name={league.name} avatar={league.avatar} />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <h2 className="truncate text-xl text-slate-100">{league.name}</h2>
            <PlatformMark provider={league.provider} label={location.label} />
          </div>
          <p className="mt-0.5 flex items-center gap-1.5 text-[11px] text-slate-400">
            <span>
              On {location.hostedOn}
              {league.scoring_type ? ` · ${league.scoring_type}` : ""} · Week {league.current_week}
            </span>
          </p>
          <p className="truncate text-[11px] text-slate-500">{team?.team.name ?? league.user_team_name ?? "Your team"}</p>
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-surface-border/70 px-4 py-2 text-[11px]">
        {location.href ? (
          <a
            href={location.href}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 font-medium text-brand hover:underline"
          >
            Open on {location.label}
            <ExternalLink className="h-3 w-3" />
          </a>
        ) : (
          <span className="text-slate-500">Hosted in this app</span>
        )}
        <Link href="/team" onClick={onSelect} className="text-slate-300 hover:text-slate-100 hover:underline">
          Roster
        </Link>
        <Link href="/matchup" onClick={onSelect} className="text-slate-300 hover:text-slate-100 hover:underline">
          Matchup
        </Link>
        <Link href="/dashboard" onClick={onSelect} className="text-slate-300 hover:text-slate-100 hover:underline">
          Dashboard
        </Link>
      </div>

      <div className="px-4 py-3">
        {loading ? (
          <div className="h-16 animate-pulse bg-surface-overlay" />
        ) : error ? (
          <p className="text-xs text-red-300">{error.message}</p>
        ) : (
          <Scorebug matchup={matchup} teamName={team?.team.name ?? league.user_team_name} record={team?.team.record} projected={team?.projected_points} live={live} />
        )}
      </div>

      {issues ? (
        <p className="px-4 pb-2 text-[11px] font-medium text-red-300">
          {issues} lineup {issues === 1 ? "issue" : "issues"}
        </p>
      ) : null}

      <ul className="mt-auto divide-y divide-surface-border/50 border-t border-surface-border">
        {loading ? (
          <li className="px-4 py-6 text-center text-[11px] text-slate-500">Loading starters…</li>
        ) : (team?.starters.length ?? 0) === 0 ? (
          <li className="px-4 py-6 text-center text-[11px] text-slate-500">No starters synced</li>
        ) : (
          team?.starters.map((slot, index) => {
            const problem = slotHasProblem(slot);
            return (
              <li
                key={`${slot.slot}-${slot.player?.id ?? index}`}
                className={cn("flex items-center gap-2 px-4 py-1.5 text-xs", problem && "bg-red-500/10")}
              >
                <PositionBadge position={slot.slot} className="min-w-[2.75rem] px-1 py-0 text-[10px]" />
                {slot.player ? <PlayerFace url={slot.player.headshot_url} name={slot.player.name} size="sm" /> : null}
                <span className="min-w-0 flex-1" title={slot.player ? seasonTitle(slot.player) : undefined}>
                  {slot.player ? (
                    <PlayerName id={slot.player.id} name={slot.player.name} className="block truncate text-slate-100" />
                  ) : (
                    <span className="block truncate text-slate-500">Empty</span>
                  )}
                  {slot.player ? (
                    <span className="block truncate text-[10px] text-slate-500">
                      {slot.player.nfl_team ?? "FA"}
                      {opponentLabel(slot.player, team?.week) ? ` · ${opponentLabel(slot.player, team?.week)}` : ""}
                    </span>
                  ) : null}
                </span>
                <span className="w-10 text-right tabular-nums text-slate-200">{formatPoints(slot.points)}</span>
              </li>
            );
          })
        )}
      </ul>
    </article>
  );
}

function Scorebug({
  matchup,
  teamName,
  record,
  projected,
  live,
}: {
  matchup?: Matchup | null;
  teamName?: string | null;
  record?: string;
  projected?: number | null;
  live: boolean;
}) {
  if (!matchup) {
    return <p className="text-xs text-slate-500">No matchup for this week yet.</p>;
  }
  if (matchup.is_bye || !matchup.opponent) {
    return (
      <div className="border border-surface-border bg-surface px-3 py-3">
        <p className="text-[10px] uppercase tracking-widest text-slate-500">Week {matchup.week}</p>
        <p className="mt-1 text-sm font-semibold text-slate-100">{teamName ?? matchup.user.team.name}</p>
        <p className="text-xs text-slate-400">Bye week</p>
      </div>
    );
  }
  const userPoints = matchup.user.points;
  const oppPoints = matchup.opponent.points;
  const ahead = userPoints > oppPoints;
  return (
    <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 border border-surface-border bg-surface px-3 py-3">
      <ScoreSide
        name={teamName ?? matchup.user.team.name}
        record={record ?? matchup.user.team.record}
        points={userPoints}
        projected={projected ?? matchup.user.projected_points}
        leading={ahead}
      />
      <div className="px-1 text-center">
        <p className={cn("text-[10px] font-semibold uppercase tracking-widest", live ? "text-red-400" : "text-slate-500")}>
          {live ? "Live" : matchup.status === "final" ? "Final" : "Week"}
        </p>
        <p className="text-[11px] text-slate-600">vs</p>
      </div>
      <ScoreSide
        name={matchup.opponent.team.name}
        record={matchup.opponent.team.record}
        points={oppPoints}
        projected={matchup.opponent.projected_points}
        leading={!ahead && oppPoints !== userPoints}
        align="right"
      />
    </div>
  );
}

function ScoreSide({
  name,
  record,
  points,
  projected,
  leading,
  align = "left",
}: {
  name: string;
  record: string;
  points: number;
  projected: number | null;
  leading: boolean;
  align?: "left" | "right";
}) {
  return (
    <div className={cn("min-w-0", align === "right" && "text-right")}>
      <p className="truncate text-xs font-medium text-slate-200">{name}</p>
      <p className="text-[10px] text-slate-500">{record}</p>
      <p className={cn("font-serif text-3xl tabular-nums leading-none", leading ? "text-slate-100" : "text-slate-400")}>
        {formatPoints(points)}
      </p>
      <p className="mt-1 text-[10px] tabular-nums text-slate-500">proj {formatPoints(projected)}</p>
    </div>
  );
}
