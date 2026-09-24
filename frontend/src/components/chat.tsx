"use client";

import { api } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";
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
  "Set this week's lineup",
];

interface Entry extends ChatMessage {
  tools_used?: string[];
  generated_by?: string;
}

export function Chat({ leagueId, aiEnabled }: { leagueId: string; aiEnabled: boolean | undefined }) {
  const [messages, setMessages] = useState<Entry[]>([]);
  const [input, setInput] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>(STARTERS);
  const bottomRef = useRef<HTMLDivElement>(null);
  const qc = useQueryClient();

  const send = useMutation({
    mutationFn: (history: ChatMessage[]) => api.ai.chat(leagueId, history),
    onSuccess: (resp) => {
      setMessages((m) => [...m, { role: "assistant", content: resp.message, tools_used: resp.tools_used, generated_by: resp.generated_by }]);
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
    send.mutate(next.map(({ role, content }) => ({ role, content })).slice(-20));
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
                ? " A free Gemini key is not configured, so replies stay rule-based and cannot change the lineup."
                : " Ask it to start, bench, or move a player and it will change this week's Sleeper lineup."}
            </p>
          </div>
        ) : (
          messages.map((m, i) => <Bubble key={i} entry={m} />)
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

function Bubble({ entry }: { entry: Entry }) {
  const isUser = entry.role === "user";
  return (
    <div className={cn("flex items-start gap-3", isUser && "flex-row-reverse")} data-testid={`msg-${entry.role}`}>
      <Avatar role={entry.role} />
      <div className={cn("max-w-[85%] px-4 py-3 text-sm", isUser ? "bg-brand text-slate-950" : "bg-surface-overlay text-slate-200")}>
        {isUser ? <p className="whitespace-pre-wrap">{entry.content}</p> : <div className="prose-chat"><ReactMarkdown>{entry.content}</ReactMarkdown></div>}
        {!isUser && entry.tools_used?.length ? (
          <p className="mt-2 border-t border-surface-border/60 pt-2 text-[10px] text-slate-500">Used: {entry.tools_used.join(", ")}</p>
        ) : null}
      </div>
    </div>
  );
}
