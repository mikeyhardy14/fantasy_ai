import { TransactionList } from "@/components/transaction-list";
import type { Transaction } from "@/lib/types";
import { render, screen } from "@testing-library/react";

function tx(overrides: Partial<Transaction>): Transaction {
  return {
    id: "tx",
    type: "waiver",
    status: "complete",
    week: 3,
    created_at: "2026-09-20T00:00:00Z",
    adds: [],
    drops: [],
    team_names: [],
    faab_bid: null,
    involves_user: false,
    ...overrides,
  };
}

describe("TransactionList", () => {
  it("shows a face for an add and a drop, and groups a trade by team", () => {
    render(
      <TransactionList
        txs={[
          tx({
            id: "waiver",
            faab_bid: 18,
            team_names: ["Mike's Marauders"],
            adds: [
              {
                player_id: "add",
                player_name: "Flash Backup",
                position: "RB",
                team_id: "1",
                team_name: "Mike's Marauders",
                headshot_url: "https://sleepercdn.com/content/nfl/players/thumb/2003.jpg",
              },
            ],
            drops: [
              {
                player_id: "drop",
                player_name: "Dropped Guy",
                position: "WR",
                team_id: "1",
                team_name: "Mike's Marauders",
                headshot_url: "https://sleepercdn.com/content/nfl/players/thumb/9999.jpg",
              },
            ],
          }),
          tx({
            id: "trade",
            type: "trade",
            team_names: ["Mike's Marauders", "Touchdown Titans"],
            adds: [
              {
                player_id: "rb",
                player_name: "Rex Cannon",
                position: "RB",
                team_id: "1",
                team_name: "Mike's Marauders",
                headshot_url: "https://sleepercdn.com/content/nfl/players/thumb/1.jpg",
              },
              {
                player_id: "wr",
                player_name: "Wide Out",
                position: "WR",
                team_id: "4",
                team_name: "Touchdown Titans",
                headshot_url: "https://sleepercdn.com/content/nfl/players/thumb/2.jpg",
              },
            ],
            drops: [
              {
                player_id: "wr",
                player_name: "Wide Out",
                position: "WR",
                team_id: "1",
                team_name: "Mike's Marauders",
                headshot_url: "https://sleepercdn.com/content/nfl/players/thumb/2.jpg",
              },
              {
                player_id: "rb",
                player_name: "Rex Cannon",
                position: "RB",
                team_id: "4",
                team_name: "Touchdown Titans",
                headshot_url: "https://sleepercdn.com/content/nfl/players/thumb/1.jpg",
              },
            ],
          }),
        ]}
      />,
    );

    const [waiver, trade] = screen.getAllByTestId("transaction");
    const faces = waiver.querySelectorAll("img");
    expect(faces).toHaveLength(2);
    expect(faces[0]).toHaveAttribute("src", expect.stringContaining("2003.jpg"));
    expect(faces[1]).toHaveAttribute("src", expect.stringContaining("9999.jpg"));
    expect(waiver).toHaveTextContent("+ Flash Backup");
    expect(waiver).toHaveTextContent("− Dropped Guy");

    const sides = trade.querySelectorAll("[data-testid='trade-side']");
    expect(sides).toHaveLength(2);
    expect(sides[0]).toHaveTextContent("Mike's Marauders");
    expect(sides[0]).toHaveTextContent("Rex Cannon");
    expect(sides[0]).toHaveTextContent("from Touchdown Titans");
    expect(sides[0]).not.toHaveTextContent("Wide Out");
    expect(sides[1]).toHaveTextContent("Wide Out");
    expect(sides[1]).toHaveTextContent("from Mike's Marauders");
    expect(trade.querySelectorAll("img")).toHaveLength(2);
  });
});
