import { LeagueChat } from "@/components/league-chat";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

describe("LeagueChat", () => {
  it("shows each manager's message in order", () => {
    render(
      <LeagueChat
        messages={[
          { id: "1", author_name: "Mike", text: "Good luck", created_at: new Date().toISOString(), pinned: true },
          { id: "2", author_name: "Rival", text: "Nice win", created_at: new Date().toISOString(), pinned: false },
        ]}
      />,
    );
    const rows = screen.getAllByTestId("league-message");
    expect(rows[0]).toHaveTextContent("Mike");
    expect(rows[0]).toHaveTextContent("Good luck");
    expect(rows[0]).toHaveTextContent("Pinned");
    expect(rows[1]).toHaveTextContent("Rival");
    expect(rows[1]).toHaveTextContent("Nice win");
  });

  it("shows the players in a proposed trade", async () => {
    const user = userEvent.setup();
    const onRespond = vi.fn();
    render(
      <LeagueChat
        onRespond={onRespond}
        messages={[
          {
            id: "t",
            author_name: "Heater911",
            text: "Heater911 offered Quinshon Judkins to Rival for TreVeyon Henderson and 2027 round 2",
            created_at: new Date().toISOString(),
            pinned: false,
            trade: {
              status: "pending",
              transaction_id: "9001",
              involves_user: true,
              sides: [
                {
                  manager: "Heater911",
                  receives: [{ name: "TreVeyon Henderson", position: "RB", headshot_url: "https://example.com/12529.jpg" }],
                  picks: ["2027 round 2"],
                },
                {
                  manager: "Rival",
                  receives: [{ name: "Quinshon Judkins", position: "RB" }],
                  picks: [],
                },
              ],
            },
          },
        ]}
      />,
    );
    expect(screen.getByTestId("league-message")).toHaveTextContent("Quinshon Judkins");
    expect(screen.getByTestId("league-message")).toHaveTextContent("TreVeyon Henderson");
    const card = screen.getByTestId("chat-trade");
    expect(card).toHaveTextContent("Heater911 receives");
    expect(card).toHaveTextContent("TreVeyon Henderson");
    expect(card).toHaveTextContent("2027 round 2");
    expect(card).toHaveTextContent("Rival receives");
    expect(card).toHaveTextContent("Quinshon Judkins");
    expect(card.querySelector("img")).toHaveAttribute("src", "https://example.com/12529.jpg");
    await user.click(screen.getByTestId("trade-accept"));
    expect(onRespond).toHaveBeenCalledWith("9001", "accept");
    await user.click(screen.getByTestId("trade-decline"));
    expect(onRespond).toHaveBeenCalledWith("9001", "decline");
  });
});
