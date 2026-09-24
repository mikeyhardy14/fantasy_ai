import { AnalysisCards } from "@/components/analysis-cards";
import { BriefingCard } from "@/components/briefing-card";
import { RecommendationCard } from "@/components/recommendation-card";
import { RosterTable } from "@/components/roster-table";
import { FlagBadges, PositionBadge } from "@/components/ui/badge";
import { ErrorState } from "@/components/ui/states";
import { ApiError } from "@/lib/api";
import { render, screen, within } from "@testing-library/react";
import { analysis, briefing, player, recommendation, slot } from "./fixtures";

describe("RosterTable", () => {
  it("renders slots, players, flags and empty slots", () => {
    const slots = [
      slot({
        slot: "QB",
        player: player({
          name: "Quinn Arrow",
          position: "QB",
          schedule: [
            { week: 4, opponent: "BUF", home: true, spread: -3.5, total: 47.5, implied_points: 25.5 },
            { week: 5, opponent: null, home: null, spread: null, total: null, implied_points: null },
          ],
          projection_note: "Vegas implied 25.5 (O/U 47.5, spread -3.5)",
        }),
        points: 22.1,
      }),
      slot({ slot: "WR", player: player({ name: "Slot Machine", position: "WR", injury_status: "Questionable" }), flags: ["QUESTIONABLE"] }),
      slot({ slot: "TE", player: player({ name: "Bye TE", position: "TE", on_bye: true }), flags: ["BYE"] }),
      slot({ slot: "FLEX", player: null }),
    ];
    render(<RosterTable slots={slots} week={4} />);
    const rows = screen.getAllByTestId("roster-row");
    expect(rows).toHaveLength(4);
    expect(screen.getByText("Quinn Arrow")).toBeInTheDocument();
    expect(screen.getByText("4 vs BUF")).toBeInTheDocument();
    expect(screen.getByText("5 BYE")).toBeInTheDocument();
    expect(within(rows[0]).getByTitle("Vegas implied 25.5 (O/U 47.5, spread -3.5)")).toHaveTextContent("14.2");
    expect(screen.getByText("22.1")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Q")).toBeInTheDocument();
    expect(within(rows[2]).getAllByText("BYE").length).toBeGreaterThan(0);
    expect(screen.getByText("Empty slot")).toBeInTheDocument();
  });

  it("shows an empty label when there are no slots", () => {
    render(<RosterTable slots={[]} emptyLabel="Bench is empty" />);
    expect(screen.getByText("Bench is empty")).toBeInTheDocument();
  });
});

describe("badges", () => {
  it("renders position badge and flag labels", () => {
    render(
      <>
        <PositionBadge position="RB" />
        <FlagBadges flags={["OUT", "BYE"]} injury="Out (Ankle)" />
      </>,
    );
    expect(screen.getByTestId("position-badge")).toHaveTextContent("RB");
    expect(screen.getByText("OUT")).toHaveAttribute("title", "Out (Ankle)");
    expect(screen.getByText("BYE")).toBeInTheDocument();
  });
});

describe("RecommendationCard", () => {
  it("shows type, priority, title and reason", () => {
    render(<RecommendationCard rec={recommendation} />);
    expect(screen.getByText("Start / Sit")).toBeInTheDocument();
    expect(screen.getByText("HIGH")).toBeInTheDocument();
    expect(screen.getByText(recommendation.title)).toBeInTheDocument();
    expect(screen.getByText(recommendation.reason)).toBeInTheDocument();
  });
});

describe("AnalysisCards", () => {
  it("renders every section as cards", () => {
    render(<AnalysisCards result={analysis} />);
    expect(screen.getByText(analysis.analysis.team_summary)).toBeInTheDocument();
    expect(screen.getByText("Strengths")).toBeInTheDocument();
    expect(screen.getByText("Weaknesses")).toBeInTheDocument();
    expect(screen.getByText("Start Backup TE")).toBeInTheDocument();
    expect(screen.getByText("over Bye TE")).toBeInTheDocument();
    expect(screen.getByText("Spare Tight")).toBeInTheDocument();
    expect(screen.getByText("Package WR depth for a TE.")).toBeInTheDocument();
    expect(screen.getByText("Move Backup TE into TE.")).toBeInTheDocument();
    expect(screen.getByText("Bye-week data is unavailable.")).toBeInTheDocument();
    expect(screen.getByText("Rule-based")).toBeInTheDocument();
    expect(screen.getByText(/get_roster, get_roster_needs/)).toBeInTheDocument();
  });
});

describe("BriefingCard", () => {
  it("renders the generate state and then the briefing", () => {
    const onGenerate = vi.fn();
    const { rerender } = render(<BriefingCard briefing={undefined} loading={false} error={null} onGenerate={onGenerate} onRetry={vi.fn()} />);
    screen.getByRole("button", { name: "Generate" }).click();
    expect(onGenerate).toHaveBeenCalled();

    rerender(<BriefingCard briefing={briefing} loading={false} error={null} onGenerate={onGenerate} onRetry={vi.fn()} />);
    expect(screen.getByText("Week 4 briefing")).toBeInTheDocument();
    expect(screen.getByText("2 items need attention")).toBeInTheDocument();
    expect(screen.getByText("Starting TE is on bye")).toBeInTheDocument();
    expect(screen.getByText("118.3")).toBeInTheDocument();
    expect(screen.getByText("1. Spare Tight")).toBeInTheDocument();
    expect(screen.getByText("Weak")).toBeInTheDocument();
  });

  it("shows an error state with retry", () => {
    const onRetry = vi.fn();
    render(<BriefingCard briefing={undefined} loading={false} error={new ApiError(502, "provider_unavailable", "Sleeper could not be reached.")} onGenerate={vi.fn()} onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Sleeper could not be reached.");
    screen.getByRole("button", { name: "Try again" }).click();
    expect(onRetry).toHaveBeenCalled();
  });
});

describe("ErrorState", () => {
  it("prefers ApiError messages", () => {
    render(<ErrorState error={new ApiError(404, "not_found", "League not found.")} />);
    expect(screen.getByText("League not found.")).toBeInTheDocument();
  });
});
