/** Sleeper often keeps last week's number until Wednesday. Tuesday ET, after that slate is final, is next week. */

export function boardWeek(
  providerWeek: number,
  nfl?: { state: string | null }[] | null,
  now: Date = new Date(),
): number {
  const week = Math.min(18, Math.max(1, providerWeek));
  const slateFinal = Boolean(nfl?.length) && nfl.every((game) => game.state === "post");
  if (!slateFinal || week >= 18) return week;
  const day = new Intl.DateTimeFormat("en-US", { weekday: "short", timeZone: "America/New_York" }).format(now);
  if (day === "Sun" || day === "Mon") return week;
  return week + 1;
}
