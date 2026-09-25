import { activeMention, annotateTeamMentions, filterTeams, insertMention, mentionIsComplete, type MentionTeam } from "@/lib/team-mentions";

const titans: MentionTeam = { id: "team-4", name: "Touchdown Titans", owner_name: "Sam", record: "4-2" };
const city: MentionTeam = { id: "team-9", name: "Touchdown City", owner_name: "Ada", record: "2-4" };

describe("team mentions", () => {
  it("opens on @ and inserts the team the cursor is on", () => {
    expect(activeMention("Look at @Tou", 12)).toEqual({ start: 8, query: "Tou" });
    expect(activeMention("email@team.com", 13)).toBeNull();
    expect(filterTeams([titans, city], "city").map((team) => team.id)).toEqual(["team-9"]);
    expect(insertMention("Look at @Tou", 12, 8, "Touchdown Titans")).toEqual({
      text: "Look at @Touchdown Titans ",
      cursor: 26,
    });
    expect(mentionIsComplete("Touchdown Titans who", [titans, city])).toBe(true);
    expect(mentionIsComplete("Touchdown Tit", [titans, city])).toBe(false);
  });

  it("adds the team id once for the assistant", () => {
    const once = annotateTeamMentions("How does @Touchdown Titans look?", [titans, city]);
    expect(once).toBe("How does @Touchdown Titans (team_id team-4) look?");
    expect(annotateTeamMentions(once, [titans, city])).toBe(once);
  });
});
