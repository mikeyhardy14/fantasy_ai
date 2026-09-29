import { DirectChatList, DirectThread } from "@/components/chat/direct-chat";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

describe("Direct chats", () => {
  it("lists other managers and shows a thread with you on your own messages", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <DirectChatList
        selectedId={null}
        onSelect={onSelect}
        chats={[
          { user_id: "2", name: "Rival", team_name: "Rival", thread_id: "dm-rival", last_message_at: new Date().toISOString() },
          { user_id: "3", name: "Quiet", team_name: "Bench Mob", thread_id: null, last_message_at: null },
        ]}
      />,
    );
    expect(screen.getByRole("button", { name: /Rival/ })).toBeInTheDocument();
    expect(screen.getByText("Quiet")).toBeInTheDocument();
    expect(screen.getByText("Bench Mob")).toBeInTheDocument();
    expect(screen.getByText("New")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Rival/ }));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ user_id: "2" }));

    render(
      <DirectChatList
        selectedId={null}
        onSelect={vi.fn()}
        autoIds={new Set(["3"])}
        onToggleAuto={onSelect}
        chats={[
          { user_id: "2", name: "Rival", team_name: "Rival", thread_id: "dm-rival", last_message_at: null },
          { user_id: "3", name: "Quiet", team_name: "Bench Mob", thread_id: null, last_message_at: null },
        ]}
      />,
    );
    expect(screen.getByRole("checkbox", { name: "Auto reply to Quiet" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Auto reply to Rival" })).not.toBeChecked();
    await user.click(screen.getByRole("checkbox", { name: "Auto reply to Rival" }));
    expect(onSelect).toHaveBeenCalledWith("2");

    render(
      <DirectThread
        messages={[
          { id: "1", author_name: "Rival", text: "You there?", created_at: new Date().toISOString(), pinned: false, mine: false },
          { id: "2", author_name: "Mike", text: "Yeah", created_at: new Date().toISOString(), pinned: false, mine: true },
        ]}
      />,
    );
    const rows = screen.getAllByTestId("direct-message");
    expect(rows[0]).toHaveAttribute("data-mine", "false");
    expect(rows[0]).toHaveTextContent("You there?");
    expect(rows[0]).toHaveClass("items-start");
    expect(rows[1]).toHaveAttribute("data-mine", "true");
    expect(rows[1]).toHaveTextContent("Yeah");
    expect(rows[1]).toHaveClass("ml-auto");
  });
});
