// Mirrors backend Pydantic schemas (app/schemas). Keep in sync.

export interface User {
  id: string;
  email: string;
  name: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface FantasyAccount {
  id: string;
  provider: string;
  external_user_id: string;
  username: string;
  display_name: string | null;
  avatar: string | null;
  created_at: string;
  last_synced_at: string | null;
  writes_enabled: boolean;
}

export interface ProviderLeague {
  external_league_id: string;
  name: string;
  season: number;
  team_count: number;
  status: string | null;
  avatar: string | null;
  scoring_type: string | null;
  imported: boolean;
}

export interface ProviderLeaguesResponse {
  account: FantasyAccount;
  season: number;
  leagues: ProviderLeague[];
}

export interface League {
  id: string;
  provider: string;
  external_league_id: string;
  name: string;
  season: number;
  team_count: number;
  current_week: number;
  status: string | null;
  avatar: string | null;
  scoring_type: string | null;
  last_synced_at: string | null;
  sync_status: "idle" | "syncing" | "success" | "error";
  sync_error: string | null;
  user_team_id: string | null;
  user_team_name: string | null;
}

export interface LeagueDetail extends League {
  scoring_settings: Record<string, number>;
  roster_settings: Record<string, unknown> & { roster_positions?: string[]; lineup_slots?: string[] };
  league_settings: Record<string, unknown>;
  account: FantasyAccount;
}

export interface Player {
  id: string;
  name: string;
  position: string | null;
  fantasy_positions: string[];
  nfl_team: string | null;
  status: string | null;
  injury_status: string | null;
  injury_body_part: string | null;
  age: number | null;
  years_exp: number | null;
  bye_week: number | null;
  on_bye: boolean;
  opponent: string | null;
  projected_points: number | null;
  projection_note: string | null;
  season_points: number | null;
  points_per_game: number | null;
  headshot_url: string | null;
  schedule: ScheduleGame[];
  projection_reasons: string[];
  projection_lines: PropLine[];
  external_ids: Record<string, string>;
}

export interface PropLine {
  label: string;
  line: number;
  weight: number;
  points: number;
  odds?: string | null;
  probability?: number | null;
}

export interface RecentGame {
  week: number;
  opponent: string | null;
  home: boolean | null;
  fantasy_points: number | null;
  points_label: string;
  summary: string;
  stats: Record<string, number>;
}

export interface PlayerSheet {
  player: Player;
  recent_games: RecentGame[];
  games_note: string | null;
}

export interface RankingRow {
  rank: number;
  player_id: string;
  name: string;
  position: string | null;
  nfl_team: string | null;
  opponent: string | null;
  home: boolean | null;
  headshot_url: string | null;
  injury_status: string | null;
  total: number | null;
  spread: number | null;
  implied_points: number | null;
  win_probability: number | null;
  book_count: number;
  books: string[];
  projected_points: number | null;
  projection_source: string | null;
  vorp: number | null;
}

export interface Rankings {
  week: number;
  notes: string[];
  rows: RankingRow[];
}

export interface ScheduleGame {
  week: number;
  opponent: string | null;
  home: boolean | null;
  spread: number | null;
  total: number | null;
  implied_points: number | null;
}

export type Flag =
  | "BYE"
  | "IR"
  | "OUT"
  | "SUSPENDED"
  | "DOUBTFUL"
  | "QUESTIONABLE"
  | "INJURED"
  | "INACTIVE"
  | "FREE_AGENT_NFL";

export interface RosterSlot {
  slot: string;
  slot_index: number | null;
  is_starter: boolean;
  player: Player | null;
  points: number | null;
  flags: Flag[];
}

export interface TeamSummary {
  id: string;
  name: string;
  owner_name: string | null;
  avatar: string | null;
  wins: number;
  losses: number;
  ties: number;
  record: string;
  points_for: number;
  points_against: number;
  faab_remaining: number | null;
  waiver_position: number | null;
  is_user_team: boolean;
}

export interface Team {
  team: TeamSummary;
  week: number;
  starters: RosterSlot[];
  bench: RosterSlot[];
  reserve: RosterSlot[];
  lineup_slots: string[];
  lineup_issues: string[];
  projected_points: number | null;
  projection_coverage: "full" | "partial" | "none";
}

export interface LineupUpdate {
  team: Team;
  verified: boolean | null;
  public_api_confirmed: boolean | null;
  message: string;
}

export interface MatchupSide {
  team: TeamSummary;
  points: number;
  projected_points: number | null;
  starters: RosterSlot[];
}

export interface Matchup {
  week: number;
  is_bye: boolean;
  user: MatchupSide;
  opponent: MatchupSide | null;
  status: "upcoming" | "in_progress" | "final" | "bye";
}

export interface StandingsRow extends TeamSummary {
  rank: number;
}

export interface TransactionPlayer {
  player_id: string | null;
  player_name: string | null;
  position: string | null;
  team_id: string | null;
  team_name: string | null;
}

export interface Transaction {
  id: string;
  type: string;
  status: string;
  week: number | null;
  created_at: string;
  adds: TransactionPlayer[];
  drops: TransactionPlayer[];
  team_names: string[];
  faab_bid: number | null;
  involves_user: boolean;
}

export interface PositionNeed {
  position: string;
  required_starters: number;
  healthy_starters: number;
  total_depth: number;
  healthy_depth: number;
  grade: "Strong" | "Adequate" | "Needs depth" | "Weak";
  notes: string[];
}

export interface RosterNeeds {
  positions: PositionNeed[];
  weakest_positions: string[];
  strongest_positions: string[];
  surplus_positions: string[];
  open_roster_spots: number;
  roster_size: number;
  max_roster_size: number | null;
}

export type RecommendationType =
  | "START_SIT"
  | "ADD_PLAYER"
  | "DROP_PLAYER"
  | "WAIVER_TARGET"
  | "TRADE_TARGET"
  | "INJURY_ALERT"
  | "BYE_WEEK"
  | "ROSTER_WEAKNESS";

export type Priority = "HIGH" | "MEDIUM" | "LOW";

export interface Recommendation {
  type: RecommendationType;
  priority: Priority;
  title: string;
  reason: string;
  players: string[];
  player_names: string[];
  position: string | null;
  data: Record<string, unknown>;
}

export interface LineupChange {
  slot: string;
  start_player: string;
  sit_player: string | null;
  reason: string;
}

export interface WaiverPriority {
  position: string;
  player_name: string | null;
  priority: Priority;
  reason: string;
}

export interface TeamAnalysis {
  team_summary: string;
  strengths: string[];
  weaknesses: string[];
  lineup_changes: LineupChange[];
  waiver_priorities: WaiverPriority[];
  trade_strategy: { can_trade_away: string[]; should_target: string[]; reasoning: string };
  this_week: string[];
  data_gaps: string[];
  confidence: Priority;
}

export interface TeamAnalysisResponse {
  analysis: TeamAnalysis;
  recommendations: Recommendation[];
  generated_by: "openai" | "gemini" | "groq" | "deterministic";
  model: string | null;
  tools_used: string[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  message: string;
  tools_used: string[];
  generated_by: "openai" | "gemini" | "groq" | "deterministic";
  suggested_questions: string[];
}

export interface TradeSide {
  players: string[];
  positions: string[];
  projected_points: number | null;
  injured: string[];
}

export interface TradeAnalysis {
  verdict: "ACCEPT" | "REJECT" | "NEGOTIATE" | "UNCLEAR";
  summary: string;
  you_give: TradeSide;
  you_receive: TradeSide;
  roster_impact: string[];
  lineup_impact: string[];
  risks: string[];
  data_gaps: string[];
}

export interface TradeAnalysisResponse {
  analysis: TradeAnalysis;
  generated_by: "openai" | "gemini" | "groq" | "deterministic";
}

export interface BriefingItem {
  title: string;
  detail: string;
  priority: Priority;
  type: RecommendationType | null;
}

export interface WeeklyBriefing {
  week: number;
  team_name: string;
  record: string;
  opponent_name: string | null;
  projected_user: number | null;
  projected_opponent: number | null;
  attention_items: BriefingItem[];
  recommended_actions: string[];
  waiver_targets: string[];
  roster_assessment: { position: string; grade: string }[];
  narrative: string | null;
  generated_by: "openai" | "gemini" | "groq" | "deterministic";
}

export interface HealthResponse {
  status: string;
  environment: string;
  ai_enabled: boolean;
  ai_provider: "gemini" | "groq" | "openai" | null;
  demo_enabled: boolean;
  nfl_data_provider: string;
}
