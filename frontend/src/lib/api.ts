import type {
  ChatMessage,
  ChatResponse,
  FantasyAccount,
  HealthResponse,
  League,
  LeagueDetail,
  Matchup,
  Player,
  PlayerSheet,
  Rankings,
  ProviderLeaguesResponse,
  Recommendation,
  RosterNeeds,
  StandingsRow,
  LineupUpdate,
  Team,
  TeamAnalysisResponse,
  TokenResponse,
  TradeAnalysisResponse,
  Transaction,
  User,
  WeeklyBriefing,
} from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const TOKEN_KEY = "fantasy_ai_token";

export class ApiError extends Error {
  status: number;
  code: string;
  details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export const tokenStore = {
  get(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(TOKEN_KEY);
  },
  set(token: string) {
    window.localStorage.setItem(TOKEN_KEY, token);
  },
  clear() {
    window.localStorage.removeItem(TOKEN_KEY);
  },
};

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) headers.set("Content-Type", "application/json");
  const token = tokenStore.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "network_error", "Could not reach the server. Is the backend running?");
  }

  if (response.status === 204) return undefined as T;
  const text = await response.text();
  const body = text ? safeJson(text) : null;

  if (!response.ok) {
    const err = (body as { error?: { code?: string; message?: string; details?: Record<string, unknown> } } | null)?.error;
    if (response.status === 401 && (err?.code ?? "unauthorized") === "unauthorized" && typeof window !== "undefined") {
      tokenStore.clear();
      window.dispatchEvent(new Event("fantasy-ai:unauthorized"));
    }
    throw new ApiError(
      response.status,
      err?.code ?? "http_error",
      err?.message ?? `Request failed (${response.status})`,
      err?.details ?? {},
    );
  }
  return body as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

const qs = (params: Record<string, string | number | boolean | undefined | null>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const api = {
  health: () => request<HealthResponse>("/api/health"),

  auth: {
    register: (body: { email: string; name: string; password: string }) =>
      request<TokenResponse>("/api/auth/register", { method: "POST", body: JSON.stringify(body) }),
    login: (body: { email: string; password: string }) =>
      request<TokenResponse>("/api/auth/login", { method: "POST", body: JSON.stringify(body) }),
    me: () => request<User>("/api/auth/me"),
  },

  integrations: {
    accounts: () => request<FantasyAccount[]>("/api/integrations/accounts"),
    providers: () =>
      request<{ provider: string; implemented: boolean; capabilities: { auth_type: string } }[]>("/api/integrations/providers"),
    connectSleeper: (username: string) =>
      request<FantasyAccount>("/api/integrations/sleeper/connect", { method: "POST", body: JSON.stringify({ username }) }),
    sleeperLeagues: (season?: number) => request<ProviderLeaguesResponse>(`/api/integrations/sleeper/leagues${qs({ season })}`),
    importSleeperLeague: (externalLeagueId: string) =>
      request<League>(`/api/integrations/sleeper/leagues/${encodeURIComponent(externalLeagueId)}/import`, { method: "POST" }),
    saveSleeperToken: (token: string, accountId?: string) =>
      request<FantasyAccount>(`/api/integrations/sleeper/token${qs({ account_id: accountId })}`, {
        method: "PUT",
        body: JSON.stringify({ token }),
      }),
    clearSleeperToken: (accountId?: string) =>
      request<FantasyAccount>(`/api/integrations/sleeper/token${qs({ account_id: accountId })}`, { method: "DELETE" }),
  },

  demo: {
    createLeague: () => request<League>("/api/demo/league", { method: "POST" }),
  },

  leagues: {
    list: () => request<League[]>("/api/leagues"),
    get: (id: string) => request<LeagueDetail>(`/api/leagues/${id}`),
    team: (id: string, week?: number) => request<Team>(`/api/leagues/${id}/team${qs({ week })}`),
    matchup: (id: string, week?: number) => request<Matchup | null>(`/api/leagues/${id}/matchup${qs({ week })}`),
    players: (id: string, params: { position?: string; search?: string; available?: boolean; limit?: number } = {}) =>
      request<Player[]>(`/api/leagues/${id}/players${qs(params)}`),
    playerSheet: (id: string, playerId: string, week?: number) =>
      request<PlayerSheet>(`/api/leagues/${id}/players/${playerId}${qs({ week })}`),
    rankings: (id: string, params: { week?: number; position?: string } = {}) =>
      request<Rankings>(`/api/leagues/${id}/rankings${qs(params)}`),
    standings: (id: string) => request<StandingsRow[]>(`/api/leagues/${id}/standings`),
    transactions: (id: string, limit = 25) => request<Transaction[]>(`/api/leagues/${id}/transactions${qs({ limit })}`),
    needs: (id: string) => request<RosterNeeds>(`/api/leagues/${id}/needs`),
    recommendations: (id: string) => request<Recommendation[]>(`/api/leagues/${id}/recommendations`),
    briefing: (id: string) => request<WeeklyBriefing>(`/api/leagues/${id}/briefing`),
    sync: (id: string) => request<{ league: League; message: string }>(`/api/leagues/${id}/sync`, { method: "POST" }),
    setLineup: (id: string, week: number, starterPlayerIds: (string | null)[]) =>
      request<LineupUpdate>(`/api/leagues/${id}/lineup`, {
        method: "POST",
        body: JSON.stringify({ week, starter_player_ids: starterPlayerIds }),
      }),
    movePlayer: (
      id: string,
      body: { week: number; player_id: string; destination: "starter" | "bench" | "ir"; slot_index?: number },
    ) => request<LineupUpdate>(`/api/leagues/${id}/lineup/move`, { method: "POST", body: JSON.stringify(body) }),
  },

  ai: {
    analyze: (leagueId: string) => request<TeamAnalysisResponse>(`/api/leagues/${leagueId}/ai/analyze`, { method: "POST" }),
    chat: (leagueId: string, messages: ChatMessage[]) =>
      request<ChatResponse>(`/api/leagues/${leagueId}/ai/chat`, { method: "POST", body: JSON.stringify({ messages }) }),
    trade: (leagueId: string, body: { give: string[]; receive: string[] }) =>
      request<TradeAnalysisResponse>(`/api/leagues/${leagueId}/ai/trade`, { method: "POST", body: JSON.stringify(body) }),
  },
};
