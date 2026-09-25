export interface MentionTeam {
  id: string;
  name: string;
  owner_name: string | null;
  record: string;
}

export function activeMention(text: string, cursor: number): { start: number; query: string } | null {
  const upto = text.slice(0, cursor);
  const at = upto.lastIndexOf("@");
  if (at < 0) return null;
  const before = at === 0 ? "" : upto[at - 1];
  if (before && !/\s/.test(before)) return null;
  const query = upto.slice(at + 1);
  if (query.includes("\n")) return null;
  return { start: at, query };
}

export function mentionIsComplete(query: string, teams: MentionTeam[]): boolean {
  const lower = query.toLowerCase();
  const named = [...teams].sort((left, right) => right.name.length - left.name.length);
  return named.some((team) => {
    const name = team.name.toLowerCase();
    return lower.startsWith(name) && lower.slice(name.length).startsWith(" ");
  });
}

export function filterTeams(teams: MentionTeam[], query: string): MentionTeam[] {
  const needle = query.trim().toLowerCase();
  return teams
    .filter((team) => {
      if (!needle) return true;
      return team.name.toLowerCase().includes(needle) || (team.owner_name ?? "").toLowerCase().includes(needle);
    })
    .slice(0, 8);
}

export function insertMention(text: string, cursor: number, start: number, name: string): { text: string; cursor: number } {
  const next = `${text.slice(0, start)}@${name} ${text.slice(cursor)}`;
  return { text: next, cursor: start + name.length + 2 };
}

export function annotateTeamMentions(text: string, teams: MentionTeam[]): string {
  const ordered = [...teams].sort((left, right) => right.name.length - left.name.length);
  let out = text;
  for (const team of ordered) {
    const token = `@${escapeRegExp(team.name)}(?! \\(team_id )`;
    out = out.replace(new RegExp(token, "g"), `@${team.name} (team_id ${team.id})`);
  }
  return out;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
