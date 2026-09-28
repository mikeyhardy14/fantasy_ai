import { AutoReplyNotes } from "@/components/auto-reply-notes";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

describe("Auto reply notes", () => {
  it("saves a voice note for one manager", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    render(
      <AutoReplyNotes
        onSave={onSave}
        people={[{ userId: "2", name: "Rival", note: "" }]}
      />,
    );
    const field = screen.getByRole("textbox", { name: "How to talk to Rival" });
    await user.type(field, "Keep it short. No trade talk.");
    await user.tab();
    expect(onSave).toHaveBeenCalledWith("2", "Keep it short. No trade talk.");
  });
});
