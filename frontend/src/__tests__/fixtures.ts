import type { Player, Recommendation, RosterSlot, TeamAnalysisResponse, WeeklyBriefing } from "@/lib/types";

export function player(overrides: Partial<Player> = {}): Player {
  return {
    id: overrides.id ?? crypto.randomUUID(),
    name: "Test Player",
    position: "RB",
    fantasy_positions: ["RB"],
    nfl_team: "KC",
    status: "Active",
    injury_status: null,
    injury_body_part: null,
    age: 25,
    years_exp: 3,
    bye_week: 7,
    on_bye: false,
    opponent: "BUF",
    projected_points: 14.2,
    projection_note: null,
    season_points: 40.1,
    points_per_game: 13.4,
    headshot_url: null,
    schedule: [],
    projection_reasons: [],
    projection_lines: [],
    external_ids: { sleeper: "1234" },
    ...overrides,
  };
}

export function slot(overrides: Partial<RosterSlot> = {}): RosterSlot {
  return { slot: "RB", slot_index: 1, is_starter: true, player: player(), points: null, flags: [], ...overrides };
}

export const recommendation: Recommendation = {
  type: "START_SIT",
  priority: "HIGH",
  title: "Start Backup TE over Bye TE at TE",
  reason: "Bye TE is on bye; Backup TE is healthy and eligible for TE.",
  players: ["a", "b"],
  player_names: ["Backup TE", "Bye TE"],
  position: "TE",
  data: { slot: "TE" },
};

export const analysis: TeamAnalysisResponse = {
  generated_by: "deterministic",
  model: null,
  tools_used: ["get_roster", "get_roster_needs"],
  recommendations: [recommendation],
  analysis: {
    team_summary: "Gridiron Gurus is 2-1 and faces Rivals in Week 4.",
    strengths: ["WR: 5 healthy players for 2 starting slot(s)."],
    weaknesses: ["TE is weak: only 1 healthy TE."],
    lineup_changes: [{ slot: "TE", start_player: "Backup TE", sit_player: "Bye TE", reason: "Bye week." }],
    waiver_priorities: [{ position: "TE", player_name: "Spare Tight", priority: "HIGH", reason: "TE depth." }],
    trade_strategy: { can_trade_away: ["WR"], should_target: ["TE"], reasoning: "Package WR depth for a TE." },
    this_week: ["Move Backup TE into TE.", "Check WR2 status."],
    data_gaps: ["Bye-week data is unavailable."],
    confidence: "MEDIUM",
  },
};

export const briefing: WeeklyBriefing = {
  week: 4,
  team_name: "Gridiron Gurus",
  record: "2-1",
  opponent_name: "Rivals",
  projected_user: 118.3,
  projected_opponent: 112.7,
  attention_items: [
    { title: "WR2 is questionable", detail: "Hamstring", priority: "MEDIUM", type: "INJURY_ALERT" },
    { title: "Starting TE is on bye", detail: "Week 4 bye", priority: "HIGH", type: "BYE_WEEK" },
  ],
  recommended_actions: ["Consider Backup TE at TE"],
  waiver_targets: ["Spare Tight"],
  roster_assessment: [{ position: "QB", grade: "Strong" }, { position: "TE", grade: "Weak" }],
  narrative: null,
  generated_by: "deterministic",
};
