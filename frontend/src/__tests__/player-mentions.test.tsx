import { MentionDirectory, MentionText, splitMentions, type MentionedPlayer } from "@/components/player/player-mentions";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

const chase: MentionedPlayer = { id: "p-chase", name: "Ja'Marr Chase", headshot_url: "https://cdn.example/chase.jpg" };
const brown: MentionedPlayer = { id: "p-brown", name: "Amon-Ra St. Brown", headshot_url: "https://cdn.example/brown.jpg" };
const shortBrown: MentionedPlayer = { id: "p-jaylen", name: "Jaylen Brown", headshot_url: null };

describe("splitMentions", () => {
  it("keeps the longer name when one name sits inside another", () => {
    const parts = splitMentions("Start Amon-Ra St. Brown, sit Jaylen Brown", [shortBrown, brown]);
    expect(parts).toEqual([
      { text: "Start " },
      { player: brown },
      { text: ", sit " },
      { player: shortBrown },
    ]);
  });

  it("leaves names that are not on a roster as plain text", () => {
    expect(splitMentions("Joe Burrow is out", [chase])).toEqual([{ text: "Joe Burrow is out" }]);
  });
});

describe("MentionText", () => {
  it("shows the headshot next to a mentioned name", () => {
    render(
      <MentionDirectory players={[chase]}>
        <MentionText text="Start Ja'Marr Chase this week" />
      </MentionDirectory>,
    );
    const mention = screen.getByTestId("player-mention");
    expect(mention.querySelector("img")).toHaveAttribute("src", "https://cdn.example/chase.jpg");
    expect(mention).toHaveTextContent("Ja'Marr Chase");
    expect(screen.getByText("Start", { exact: false })).toBeInTheDocument();
  });
});
