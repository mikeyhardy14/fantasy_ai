"use client";

import { PlayerFace } from "@/components/player/player-face";
import { PlayerName } from "@/components/player/player-name";
import { useLeague } from "@/lib/league";
import { useLeagueRosters } from "@/lib/queries";
import type { Team } from "@/lib/types";
import { Children, createContext, useContext, useMemo, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";

export interface MentionedPlayer {
  id: string;
  name: string;
  headshot_url: string | null;
}

const DirectoryContext = createContext<MentionedPlayer[]>([]);

export function playersOnRosters(teams: Team[]): MentionedPlayer[] {
  const seen = new Map<string, MentionedPlayer>();
  for (const team of teams) {
    for (const slot of [...team.starters, ...team.bench, ...team.reserve]) {
      const player = slot.player;
      if (!player || player.name.length < 3 || seen.has(player.name)) continue;
      seen.set(player.name, { id: player.id, name: player.name, headshot_url: player.headshot_url });
    }
  }
  return [...seen.values()].sort((left, right) => right.name.length - left.name.length);
}

export function MentionDirectory({ players, children }: { players: MentionedPlayer[]; children: ReactNode }) {
  return <DirectoryContext.Provider value={players}>{children}</DirectoryContext.Provider>;
}

export function usePlayerDirectory() {
  return useContext(DirectoryContext);
}

export function PlayerDirectory({ children }: { children: ReactNode }) {
  const { selected } = useLeague();
  const rosters = useLeagueRosters(selected?.id);
  const players = useMemo(() => playersOnRosters(rosters.data ?? []), [rosters.data]);
  return <MentionDirectory players={players}>{children}</MentionDirectory>;
}

export function InlinePlayer({ id, name, headshot }: { id?: string | null; name: string; headshot?: string | null }) {
  return (
    <span className="inline-flex items-center gap-1 align-middle" data-testid="player-mention">
      <PlayerFace url={headshot ?? null} name={name} size="xs" />
      {id ? <PlayerName id={id} name={name} /> : name}
    </span>
  );
}

export function splitMentions(text: string, players: MentionedPlayer[]): Array<{ text: string } | { player: MentionedPlayer }> {
  const named = players.filter((player) => player.name.length >= 3).sort((left, right) => right.name.length - left.name.length);
  if (!text || !named.length) return [{ text }];
  const pattern = named.map((player) => player.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|");
  const expression = new RegExp(`(?<![A-Za-z])(?:${pattern})(?![A-Za-z])`, "g");
  const byName = new Map(named.map((player) => [player.name, player]));
  const parts: Array<{ text: string } | { player: MentionedPlayer }> = [];
  let cursor = 0;
  for (const match of text.matchAll(expression)) {
    const index = match.index ?? 0;
    if (index > cursor) parts.push({ text: text.slice(cursor, index) });
    const player = byName.get(match[0]);
    if (player) parts.push({ player });
    else parts.push({ text: match[0] });
    cursor = index + match[0].length;
  }
  if (cursor < text.length) parts.push({ text: text.slice(cursor) });
  return parts.length ? parts : [{ text }];
}

export function MentionText({ text }: { text: string }) {
  const players = useContext(DirectoryContext);
  const parts = splitMentions(text, players);
  if (parts.length === 1 && "text" in parts[0]) return <>{parts[0].text}</>;
  return (
    <>
      {parts.map((part, index) =>
        "player" in part ? (
          <span key={index} className="inline-flex items-center gap-1 align-middle" data-testid="player-mention">
            <PlayerFace url={part.player.headshot_url} name={part.player.name} size="xs" />
            <PlayerName id={part.player.id} name={part.player.name} />
          </span>
        ) : (
          <span key={index}>{part.text}</span>
        ),
      )}
    </>
  );
}

function faceChildren(children: ReactNode) {
  return Children.map(children, (child) => (typeof child === "string" ? <MentionText text={child} /> : child));
}

export function FacedMarkdown({ text }: { text: string }) {
  return (
    <ReactMarkdown
      components={{
        p: ({ children }) => <p>{faceChildren(children)}</p>,
        li: ({ children }) => <li>{faceChildren(children)}</li>,
        strong: ({ children }) => <strong>{faceChildren(children)}</strong>,
        em: ({ children }) => <em>{faceChildren(children)}</em>,
      }}
    >
      {text}
    </ReactMarkdown>
  );
}
