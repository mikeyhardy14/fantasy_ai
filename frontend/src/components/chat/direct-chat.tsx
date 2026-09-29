"use client";

import { MentionText } from "@/components/player/player-mentions";
import type { DirectChat, LeagueMessage } from "@/lib/types";
import { cn, relativeTime } from "@/lib/utils";
import { useEffect, useRef } from "react";

function initial(name: string): string {
  return name.replace(/[^A-Za-z]/g, "").slice(0, 1).toUpperCase() || "?";
}

export function DirectChatList({
  chats,
  selectedId,
  onSelect,
  autoIds,
  onToggleAuto,
}: {
  chats: DirectChat[];
  selectedId: string | null;
  onSelect: (chat: DirectChat) => void;
  autoIds?: ReadonlySet<string>;
  onToggleAuto?: (userId: string) => void;
}) {
  if (!chats.length) {
    return <p className="px-4 py-6 text-sm text-slate-400">No other managers in this league.</p>;
  }
  return (
    <ul data-testid="direct-list">
      {chats.map((chat) => {
        const active = selectedId === chat.user_id;
        return (
          <li key={chat.user_id} className="flex items-stretch">
            <button
              type="button"
              onClick={() => onSelect(chat)}
              className={cn(
                "flex min-w-0 flex-1 items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-surface-overlay/50",
                active && "bg-surface-overlay",
              )}
              data-testid="direct-manager"
            >
              <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-surface-overlay text-sm font-medium text-slate-200">
                {initial(chat.name)}
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-baseline justify-between gap-2">
                  <span className="truncate text-sm text-slate-100">{chat.name}</span>
                  <span className="shrink-0 text-[11px] text-slate-500">
                    {chat.last_message_at ? relativeTime(chat.last_message_at) : "New"}
                  </span>
                </span>
                {chat.team_name !== chat.name ? (
                  <span className="block truncate text-xs text-slate-500">{chat.team_name}</span>
                ) : (
                  <span className="block truncate text-xs text-slate-500">{chat.thread_id ? "Direct message" : "Start a chat"}</span>
                )}
              </span>
            </button>
            {onToggleAuto ? (
              <label className="flex shrink-0 flex-col items-center justify-center gap-0.5 pr-3 text-[10px] uppercase tracking-wide text-slate-500">
                Auto
                <input
                  type="checkbox"
                  className="h-4 w-4"
                  aria-label={`Auto reply to ${chat.name}`}
                  checked={autoIds?.has(chat.user_id) ?? false}
                  onChange={() => onToggleAuto(chat.user_id)}
                />
              </label>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

export function DirectThread({ messages, name }: { messages: LeagueMessage[]; name?: string }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [messages]);

  if (!messages.length) {
    return (
      <p className="px-5 py-10 text-center text-sm text-slate-400">
        {name ? `Say hello to ${name}.` : "No messages yet."}
      </p>
    );
  }
  return (
    <ol className="flex flex-col gap-2 px-4 py-4" data-testid="direct-thread">
      {messages.map((message, index) => {
        const previous = messages[index - 1];
        const showName = !message.mine && previous?.mine !== false;
        return (
          <li
            key={message.id}
            data-testid="direct-message"
            data-mine={message.mine ? "true" : "false"}
            className={cn("flex max-w-[80%] flex-col", message.mine ? "ml-auto items-end" : "mr-auto items-start")}
          >
            {showName ? <span className="mb-1 px-1 text-[11px] text-slate-500">{message.author_name}</span> : null}
            <span
              className={cn(
                "whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm",
                message.mine
                  ? "rounded-br-md bg-brand text-slate-950"
                  : "rounded-bl-md bg-surface-overlay text-slate-100",
              )}
            >
              <MentionText text={message.text} />
            </span>
            <span className="mt-1 px-1 text-[10px] text-slate-500">{relativeTime(message.created_at)}</span>
          </li>
        );
      })}
      <div ref={end} />
    </ol>
  );
}
