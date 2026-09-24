/** Where an imported league lives, and the public page for that league. */

const SAFE_ID = /^[A-Za-z0-9._-]+$/;

export interface LeagueLocation {
  provider: string;
  label: string;
  hostedOn: string;
  href: string | null;
}

const HOSTS: Record<string, { label: string; hostedOn: string; href: (id: string, season: number) => string | null }> = {
  sleeper: {
    label: "Sleeper",
    hostedOn: "sleeper.com",
    href: (id) => `https://sleeper.com/leagues/${id}`,
  },
  yahoo: {
    label: "Yahoo Fantasy",
    hostedOn: "Yahoo",
    href: (id) => `https://football.fantasysports.yahoo.com/f1/${id}`,
  },
  espn: {
    label: "ESPN Fantasy",
    hostedOn: "ESPN",
    href: (id, season) => `https://fantasy.espn.com/football/league?leagueId=${id}&seasonId=${season}`,
  },
  nfl: {
    label: "NFL Fantasy",
    hostedOn: "NFL.com",
    href: (id) => `https://fantasy.nfl.com/league/${id}`,
  },
  demo: {
    label: "Demo",
    hostedOn: "This app",
    href: () => null,
  },
};

export function leagueLocation(league: { provider: string; external_league_id: string; season: number }): LeagueLocation {
  const host = HOSTS[league.provider] ?? {
    label: league.provider,
    hostedOn: "Unknown host",
    href: () => null,
  };
  const id = league.external_league_id;
  const href = SAFE_ID.test(id) ? host.href(id, league.season) : null;
  return { provider: league.provider, label: host.label, hostedOn: host.hostedOn, href };
}

export function leagueInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

export function safeImageUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" ? parsed.toString() : null;
  } catch {
    return null;
  }
}
