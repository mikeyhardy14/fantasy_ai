"use client";

import { Chat } from "@/components/chat";
import { NoLeague } from "@/components/no-league";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { SkeletonRows } from "@/components/ui/states";
import { useLeague } from "@/lib/league";
import { useHealth } from "@/lib/queries";
import { aiStatusLabel } from "@/lib/utils";

export default function AssistantPage() {
  const { selected, loading, leagues } = useLeague();
  const health = useHealth();
  if (loading) return <SkeletonRows rows={10} />;
  if (!leagues.length || !selected) return <NoLeague />;
  return (
    <div className="space-y-6">
      <PageHeader
        title="AI Assistant"
        description={`${selected.name} · ${selected.user_team_name ?? "your team"} · Week ${selected.current_week}`}
        action={
          health.data ? (
            <Badge className={health.data.ai_enabled ? "bg-brand-soft text-emerald-200 ring-emerald-500/30" : "bg-amber-500/15 text-amber-200 ring-amber-500/30"}>
              {aiStatusLabel(health.data.ai_enabled, health.data.ai_provider)}
            </Badge>
          ) : null
        }
      />
      <Chat key={selected.id} leagueId={selected.id} aiEnabled={health.data?.ai_enabled} />
    </div>
  );
}
