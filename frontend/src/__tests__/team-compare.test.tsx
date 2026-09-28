import { CompareReadout } from "@/components/team-compare";
import type { TeamCompare } from "@/lib/types";
import { render, screen } from "@testing-library/react";

const result: TeamCompare = {
  week: 4,
  generated_by: "deterministic",
  model: null,
  summary: "Alpha is 4-0 with 520.4 points for. Alpha is ahead at RB.",
  sides: [
    {
      team_id: "a",
      name: "Alpha",
      owner_name: "Ada",
      is_user_team: true,
      record: "4-0",
      points_for: 520.4,
      points_against: 400,
      projected_points: 118.2,
      faab_remaining: 80,
      waiver_position: 6,
      starters_out: 0,
      starters_on_bye: 1,
      positions: [{ position: "RB", grade: "Strong", healthy_depth: 3, total_depth: 4, starter_projection: 18.4 }],
      starters: [{ name: "Lead Back", slot: "RB", position: "RB", projected_points: 18.4, points: 9.1, injury_status: null, on_bye: false }],
    },
    {
      team_id: "b",
      name: "Beta",
      owner_name: "Bea",
      is_user_team: false,
      record: "2-2",
      points_for: 410,
      points_against: 430,
      projected_points: 96.5,
      faab_remaining: 20,
      waiver_position: 2,
      starters_out: 1,
      starters_on_bye: 0,
      positions: [{ position: "RB", grade: "Weak", healthy_depth: 1, total_depth: 2, starter_projection: 8 }],
      starters: [{ name: "Hurt Back", slot: "RB", position: "RB", projected_points: 8, points: null, injury_status: "Out", on_bye: false }],
    },
  ],
};

describe("CompareReadout", () => {
  it("shows both teams' numbers beside the write-up", () => {
    render(<CompareReadout result={result} />);
    expect(screen.getAllByText("Alpha").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Beta").length).toBeGreaterThan(0);
    expect(screen.getByText("4-0")).toBeInTheDocument();
    expect(screen.getByText("2-2")).toBeInTheDocument();
    expect(screen.getByText("520.4")).toBeInTheDocument();
    expect(screen.getByText("118.2")).toBeInTheDocument();
    expect(screen.getByText("Strong · 3/4 healthy · 18.4 proj")).toBeInTheDocument();
    expect(screen.getByText("Lead Back")).toBeInTheDocument();
    expect(screen.getByText("Hurt Back")).toBeInTheDocument();
    expect(screen.getByTestId("compare-summary")).toHaveTextContent("ahead at RB");
  });
});
