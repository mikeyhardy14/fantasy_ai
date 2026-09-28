"use client";

import { AutoReplyNotes } from "@/components/auto-reply-notes";
import { DirectChatList, DirectThread } from "@/components/direct-chat";
import { LeagueChat, TradeCard } from "@/components/league-chat";
import { NoLeague } from "@/components/no-league";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ErrorState, SkeletonRows } from "@/components/ui/states";
import { api } from "@/lib/api";
import { useToast } from "@/components/toast";
import { useLeague } from "@/lib/league";
import { keys, useAutoReply, useDirectChats, useDirectMessages, useLeagueMessages } from "@/lib/queries";
import type { DirectChat, LeagueMessage } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useState } from "react";

export default function MessagesPage() {
  const { selected, loading, leagues } = useLeague();
  if (loading) return <SkeletonRows rows={8} />;
  if (!leagues.length || !selected) return <NoLeague />;
  return <MessagesView leagueId={selected.id} leagueName={selected.name} provider={selected.provider} />;
}

function ManagerOffers({
  messages,
  managerName,
  onRespond,
  responding,
}: {
  messages: LeagueMessage[];
  managerName: string;
  onRespond?: (transactionId: string, action: "accept" | "decline") => void;
  responding?: boolean;
}) {
  const offers = messages.filter((message) => message.trade?.sides.some((side) => side.manager === managerName));
  if (!offers.length) return null;
  return (
    <div className="space-y-3 border-b border-surface-border px-4 py-3" data-testid="manager-offers">
      {offers
        .slice()
        .reverse()
        .map((message) =>
          message.trade ? (
            <div key={message.id}>
              <p className="mb-2 text-sm text-slate-100">{message.text}</p>
              <TradeCard trade={message.trade} onRespond={onRespond} responding={responding} />
            </div>
          ) : null,
        )}
    </div>
  );
}

function MessagesView({ leagueId, leagueName, provider }: { leagueId: string; leagueName: string; provider: string }) {
  const messages = useLeagueMessages(leagueId);
  const chats = useDirectChats(leagueId);
  const auto = useAutoReply(leagueId);
  const [selected, setSelected] = useState<DirectChat | null>(null);
  const [draft, setDraft] = useState("");
  const queryClient = useQueryClient();
  const toast = useToast();
  const saveAuto = useMutation({
    mutationFn: (body: { enabled: boolean; user_ids: string[]; notes?: Record<string, string> }) =>
      api.leagues.saveAutoReply(leagueId, body),
    onSuccess: (result, body) => {
      queryClient.setQueryData(keys.autoReply(leagueId), result);
      if (body.enabled !== auto.data?.enabled) toast(result.enabled ? "Auto AI fantasy is on." : "Auto AI fantasy is off.");
    },
  });
  const autoIds = new Set(auto.data?.user_ids ?? []);
  const notes = auto.data?.notes ?? {};
  const savePeople = (enabled: boolean, userIds: string[], nextNotes: Record<string, string>) => {
    const kept: Record<string, string> = {};
    for (const id of userIds) kept[id] = nextNotes[id] ?? "";
    saveAuto.mutate({ enabled, user_ids: userIds, notes: kept });
  };
  const toggleAuto = (enabled: boolean) => {
    if (!auto.data) return;
    savePeople(enabled, auto.data.user_ids, notes);
  };
  const togglePerson = (userId: string) => {
    if (!auto.data?.available) return;
    const ids = new Set(auto.data.user_ids);
    if (ids.has(userId)) ids.delete(userId);
    else ids.add(userId);
    savePeople(auto.data.enabled, [...ids], notes);
  };
  const saveNote = (userId: string, note: string) => {
    if (!auto.data) return;
    savePeople(auto.data.enabled, auto.data.user_ids, { ...notes, [userId]: note });
  };
  const respond = useMutation({
    mutationFn: ({ transactionId, action }: { transactionId: string; action: "accept" | "decline" }) =>
      api.leagues.respondTrade(leagueId, transactionId, action),
    onSuccess: async (result) => {
      toast(result.message);
      await queryClient.invalidateQueries({ queryKey: keys.messages(leagueId) });
    },
  });
  const onRespond = (transactionId: string, action: "accept" | "decline") => respond.mutate({ transactionId, action });
  const thread = useDirectMessages(leagueId, selected?.thread_id ?? null);
  const send = useMutation({
    mutationFn: (text: string) =>
      selected?.thread_id
        ? api.leagues.sendDirect(leagueId, selected.thread_id, text)
        : api.leagues.startDirect(leagueId, selected!.user_id, text),
    onSuccess: async (result) => {
      setDraft("");
      setSelected((current) => (current ? { ...current, thread_id: result.thread_id } : current));
      queryClient.setQueryData(keys.directThread(leagueId, result.thread_id), result.messages);
      await queryClient.invalidateQueries({ queryKey: keys.direct(leagueId) });
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Chat" description={`The ${leagueName} board, your chats, and Auto AI fantasy for the managers you check.`} />
      <AutoFantasyBar
        provider={provider}
        enabled={auto.data?.enabled ?? false}
        available={auto.data?.available ?? false}
        pending={auto.isLoading || saveAuto.isPending}
        error={saveAuto.error}
        onToggle={toggleAuto}
        people={(chats.data ?? [])
          .filter((chat) => autoIds.has(chat.user_id))
          .map((chat) => ({ userId: chat.user_id, name: chat.name, note: notes[chat.user_id] ?? "" }))}
        onNote={saveNote}
      />
      <Card className="max-h-[36rem] overflow-y-auto">
        <CardHeader title="League chat" description="What every manager can read. A trade offer lists the players." />
        {messages.isLoading ? (
          <div className="p-5">
            <SkeletonRows rows={4} />
          </div>
        ) : messages.error ? (
          <ErrorState error={messages.error} onRetry={() => messages.refetch()} />
        ) : (
          <LeagueChat
            messages={[...(messages.data ?? [])].reverse()}
            onRespond={onRespond}
            responding={respond.isPending}
          />
        )}
        {respond.error ? <p className="px-5 pb-4 text-sm text-red-300">{respond.error.message}</p> : null}
      </Card>
      <Card className="overflow-hidden">
        <div className="flex h-[36rem] min-h-0">
          <div className={cn("w-full shrink-0 overflow-y-auto border-surface-border sm:w-64 sm:border-r", selected && "hidden sm:block")}>
            <p className="px-3 pb-1 pt-3 text-[11px] uppercase tracking-wide text-slate-500">Managers</p>
            {chats.isLoading ? (
              <div className="p-3">
                <SkeletonRows rows={6} />
              </div>
            ) : chats.error ? (
              <ErrorState error={chats.error} onRetry={() => chats.refetch()} />
            ) : (
              <DirectChatList
                chats={chats.data ?? []}
                selectedId={selected?.user_id ?? null}
                autoIds={autoIds}
                onToggleAuto={auto.data?.available ? togglePerson : undefined}
                onSelect={(chat) => {
                  setDraft("");
                  send.reset();
                  setSelected(chat);
                }}
              />
            )}
          </div>
          <div className={cn("flex min-w-0 flex-1 flex-col", !selected && "hidden sm:flex")}>
            {selected ? (
              <>
                <div className="flex items-center gap-2 border-b border-surface-border px-3 py-2.5">
                  <button
                    type="button"
                    className="rounded-md p-1 text-slate-400 hover:bg-surface-overlay hover:text-slate-100 sm:hidden"
                    aria-label="Back to managers"
                    onClick={() => setSelected(null)}
                  >
                    <ArrowLeft className="h-4 w-4" />
                  </button>
                  <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-surface-overlay text-xs font-medium text-slate-200">
                    {selected.name.replace(/[^A-Za-z]/g, "").slice(0, 1).toUpperCase() || "?"}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-sm text-slate-100">{selected.name}</span>
                    <span className="block truncate text-[11px] text-slate-500">{selected.team_name}</span>
                  </span>
                </div>
                <div className="min-h-0 flex-1 overflow-y-auto">
                  <ManagerOffers
                    messages={messages.data ?? []}
                    managerName={selected.name}
                    onRespond={onRespond}
                    responding={respond.isPending}
                  />
                  {selected.thread_id && thread.isLoading ? (
                    <div className="p-5">
                      <SkeletonRows rows={4} />
                    </div>
                  ) : selected.thread_id && thread.error ? (
                    <ErrorState error={thread.error} onRetry={() => thread.refetch()} />
                  ) : (
                    <DirectThread messages={thread.data ?? []} name={selected.name} />
                  )}
                </div>
                <form
                  className="flex items-center gap-2 border-t border-surface-border px-3 py-3"
                  onSubmit={(event) => {
                    event.preventDefault();
                    const text = draft.trim();
                    if (text) send.mutate(text);
                  }}
                >
                  <Input
                    aria-label={`Message ${selected.name}`}
                    placeholder={`Message ${selected.name}`}
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    className="rounded-full"
                  />
                  <Button type="submit" data-testid="direct-send" loading={send.isPending} disabled={!draft.trim()}>
                    Send
                  </Button>
                </form>
                {send.error ? <p className="px-4 pb-3 text-sm text-red-300">{send.error.message}</p> : null}
              </>
            ) : (
              <p className="m-auto px-6 text-center text-sm text-slate-400">Choose a manager to open the chat.</p>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}

function AutoFantasyBar({
  provider,
  enabled,
  available,
  pending,
  error,
  onToggle,
  people,
  onNote,
}: {
  provider: string;
  enabled: boolean;
  available: boolean;
  pending: boolean;
  error: Error | null;
  onToggle: (enabled: boolean) => void;
  people: { userId: string; name: string; note: string }[];
  onNote: (userId: string, note: string) => void;
}) {
  const sleeper = provider === "sleeper";
  return (
    <Card data-testid="auto-fantasy">
      <CardHeader title="Auto AI fantasy" description="Replies as you after someone you check sends a new message. A note sets how that reply sounds." />
      <div className="px-5 pb-5">
        <label className="flex items-start gap-3 text-sm">
          <input
            type="checkbox"
            className="mt-1"
            data-testid="auto-fantasy-toggle"
            checked={enabled}
            disabled={!available || pending}
            onChange={(event) => onToggle(event.target.checked)}
          />
          <span>
            <span className="font-medium text-slate-100">Reply for me</span>
            <span className="mt-1 block text-xs leading-relaxed text-slate-400">
              Check Auto next to a manager. Add a note for how to talk to them. The assistant uses that note on their next private message.
            </span>
          </span>
        </label>
        {available ? <AutoReplyNotes people={people} onSave={onNote} /> : null}
        {!sleeper ? <p className="mt-3 text-xs text-amber-200">Auto AI fantasy replies in Sleeper leagues.</p> : null}
        {sleeper && !available && !pending ? (
          <p className="mt-3 text-xs text-amber-200">Save your Sleeper token in Settings. Replies are sent from your Sleeper account.</p>
        ) : null}
        {error ? <p className="mt-3 text-sm text-red-300">{error.message}</p> : null}
      </div>
    </Card>
  );
}
