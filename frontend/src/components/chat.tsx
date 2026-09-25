"use client";

import { PlayerFace } from "@/components/player-face";
import { PositionBadge } from "@/components/ui/badge";
import { api, ApiError } from "@/lib/api";
import { moveSummary, movesToApply, readLineupAutoApprove } from "@/lib/lineup-approval";
import type { ChatMessage, LineupAction } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Send } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import { Button } from "./ui/button";
import { InlineError } from "./ui/states";

const STARTERS = [
  "What should I do with my team this week?",
  "Who should I start at FLEX?",
  "What are the biggest weaknesses on my roster?",
  "What position should I target on waivers?",
  "Which bench player has the most upside?",
  "Review the trades that were made",
  "Set this week's lineup",
];

interface Entry extends ChatMessage {
  tools_used?: string[];
  generated_by?: string;
  actions?: LineupAction[];
  subResults?: string[];
  subError?: string;
  autoChecked?: boolean;
}

export function Chat({ leagueId, aiEnabled }: { leagueId: string; aiEnabled: boolean | undefined }) {
  const [messages, setMessages] = useState<Entry[]>([]);
  const [input, setInput] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>(STARTERS);
  const bottomRef = useRef<HTMLDivElement>(null);
  const applied = useRef(new Set<string>());
  const qc = useQueryClient();

  const send = useMutation({
    mutationFn: ({ history, auto }: { history: ChatMessage[]; auto: boolean }) => api.ai.chat(leagueId, history, auto),
    onSuccess: (resp) => {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: resp.message,
          tools_used: resp.tools_used,
          generated_by: resp.generated_by,
          actions: resp.actions ?? [],
        },
      ]);
      if (resp.suggested_questions.length) setSuggestions(resp.suggested_questions);
      if (resp.tools_used.some((name) => name === "change_lineup" || name === "set_lineup")) {
        void qc.invalidateQueries({ queryKey: ["league", leagueId] });
      }
    },
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, send.isPending]);

  function ask(text: string) {
    const content = text.trim();
    if (!content || send.isPending) return;
    const next: Entry[] = [...messages, { role: "user", content }];
    setMessages(next);
    setInput("");
    send.mutate({
      history: next.map(({ role, content }) => ({ role, content })).slice(-20),
      auto: readLineupAutoApprove(),
    });
  }

  const sub = useMutation({
    mutationFn: (action: LineupAction) =>
      api.leagues.movePlayer(leagueId, {
        week: action.week,
        player_id: action.player_id,
        destination: action.destination,
        slot_index: action.slot_index,
      }),
    onSuccess: (resp, action) => {
      setMessages((current) =>
        current.map((entry) =>
          entry.actions?.some((item) => sameMove(item, action))
            ? {
                ...entry,
                actions: entry.actions.filter((item) => !sameMove(item, action)),
                subResults: [...(entry.subResults ?? []), resp.message],
                subError: undefined,
              }
            : entry,
        ),
      );
      void qc.invalidateQueries({ queryKey: ["league", leagueId] });
    },
    onError: (error, action) => {
      const message = error instanceof ApiError ? error.message : "The lineup change did not go through.";
      setMessages((current) =>
        current.map((entry) =>
          entry.actions?.some((item) => sameMove(item, action)) ? { ...entry, subError: message } : entry,
        ),
      );
    },
  });

  useEffect(() => {
    if (!readLineupAutoApprove()) return;
    const waiting = messages.flatMap((entry, index) =>
      entry.autoChecked
        ? []
        : movesToApply(entry.actions ?? []).map((action) => ({
            index,
            action,
            key: `${index}:${action.player_id}:${action.slot_index}`,
          })),
    );
    const fresh = waiting.filter((item) => !applied.current.has(item.key));
    if (!fresh.length) return;
    for (const item of fresh) applied.current.add(item.key);
    const indexes = new Set(fresh.map((item) => item.index));
    setMessages((current) => current.map((entry, index) => (indexes.has(index) ? { ...entry, autoChecked: true } : entry)));
    for (const item of fresh) sub.mutate(item.action);
  }, [messages, sub]);

  function decline(action: LineupAction) {
    const note = action.replaces
      ? `Left ${action.replaces} in the lineup.`
      : `Skipped starting ${action.player_name}.`;
    setMessages((current) =>
      current.map((entry) =>
        entry.actions?.some((item) => sameMove(item, action))
          ? {
              ...entry,
              actions: entry.actions.filter((item) => !sameMove(item, action)),
              subResults: [...(entry.subResults ?? []), note],
            }
          : entry,
      ),
    );
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    ask(input);
  }

  return (
    <div className="flex h-[calc(100vh-14rem)] min-h-[28rem] flex-col border border-surface-border bg-surface-raised">
      <div className="flex-1 space-y-4 overflow-y-auto p-5">
        {!messages.length ? (
          <div className="max-w-md pt-6">
            <h3 className="text-2xl text-slate-100">Ask about this roster</h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-400">
              Answers use the imported roster, league settings, this week&apos;s matchup, and available players.
              {aiEnabled === false
                ? " A free Gemini key is not configured, so replies stay rule-based. Sub requests still list a button for each replacement."
                : " A start-over shows the move and waits for your approval. Ask it to review the trades that were made."}
            </p>
          </div>
        ) : (
          messages.map((m, i) => (
            <Bubble
              key={i}
              entry={m}
              pendingId={sub.isPending ? sub.variables?.player_id ?? null : null}
              onSub={(action) => sub.mutate(action)}
              onDecline={decline}
            />
          ))
        )}
        {send.isPending ? (
          <div className="flex items-start gap-3">
            <Avatar role="assistant" />
            <div className="border border-surface-border bg-surface-overlay px-4 py-3 text-sm text-slate-400">
              <span className="inline-flex gap-1">
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.2s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.1s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400" />
              </span>
              <span className="ml-2 text-xs">Checking your league data…</span>
            </div>
          </div>
        ) : null}
        <div ref={bottomRef} />
      </div>
      <div className="border-t border-surface-border p-3">
        <InlineError error={send.error} />
        <div className="mb-2 flex flex-wrap gap-1.5">
          {suggestions.map((s) => (
            <button key={s} onClick={() => ask(s)} disabled={send.isPending} className="border border-surface-border px-2 py-1 text-xs text-slate-300 transition hover:border-brand hover:text-slate-100 disabled:opacity-50">
              {s}
            </button>
          ))}
        </div>
        <form onSubmit={onSubmit} className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about start/sit, waivers, trades, weaknesses…"
            className="h-10 flex-1 rounded-lg border border-surface-border bg-surface px-3 text-sm text-slate-100 placeholder:text-slate-500 focus:border-brand focus:outline-none"
            aria-label="Message"
            maxLength={2000}
          />
          <Button type="submit" disabled={!input.trim()} loading={send.isPending} aria-label="Send">
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </div>
    </div>
  );
}

function Avatar({ role }: { role: "user" | "assistant" }) {
  return (
    <span className="w-10 shrink-0 pt-1 font-serif text-sm text-slate-400">{role === "assistant" ? "Desk" : "You"}</span>
  );
}

function sameMove(item: LineupAction, action: LineupAction): boolean {
  return item.player_id === action.player_id && item.slot_index === action.slot_index;
}

function Bubble({
  entry,
  pendingId,
  onSub,
  onDecline,
}: {
  entry: Entry;
  pendingId?: string | null;
  onSub?: (action: LineupAction) => void;
  onDecline?: (action: LineupAction) => void;
}) {
  const isUser = entry.role === "user";
  return (
    <div className={cn("flex items-start gap-3", isUser && "flex-row-reverse")} data-testid={`msg-${entry.role}`}>
      <Avatar role={entry.role} />
      <div className={cn("max-w-[85%] px-4 py-3 text-sm", isUser ? "bg-brand text-slate-950" : "bg-surface-overlay text-slate-200")}>
        {isUser ? <p className="whitespace-pre-wrap">{entry.content}</p> : <div className="prose-chat"><ReactMarkdown>{entry.content}</ReactMarkdown></div>}
        {entry.actions?.length ? (
          <div className="mt-3 space-y-2">
            {entry.actions.map((action) => (
              <div
                key={`${action.player_id}-${action.slot_index}`}
                data-testid="lineup-approval"
                className="border border-surface-border bg-surface px-3 py-2"
              >
                <div className="flex items-center gap-2">
                  <PositionBadge position={action.position ?? action.slot} />
                  <PlayerFace url={action.headshot_url} name={action.player_name} size="sm" />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm text-slate-100">{moveSummary(action)}</span>
                    {action.detail ? <span className="block truncate text-[11px] text-slate-500">{action.detail}</span> : null}
                  </span>
                </div>
                <div className="mt-2 flex gap-2">
                  <Button
                    size="sm"
                    data-testid="sub-action"
                    disabled={pendingId != null}
                    onClick={() => onSub?.(action)}
                  >
                    Approve
                  </Button>
                  <Button size="sm" variant="secondary" disabled={pendingId != null} onClick={() => onDecline?.(action)}>
                    Decline
                  </Button>
                </div>
              </div>
            ))}
          </div>
        ) : null}
        {entry.subResults?.map((result) => (
          <p key={result} className="mt-2 text-xs text-slate-300" data-testid="sub-result">{result}</p>
        ))}
        {entry.subError ? <p className="mt-2 text-xs text-red-700" data-testid="sub-error">{entry.subError}</p> : null}
        {!isUser && entry.tools_used?.length ? (
          <p className="mt-2 border-t border-surface-border/60 pt-2 text-[10px] text-slate-500">Used: {entry.tools_used.join(", ")}</p>
        ) : null}
      </div>
    </div>
  );
}
