import { ProposeTradeDialog } from "@/components/propose-trade";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { player } from "./fixtures";

describe("ProposeTradeDialog", () => {
  it("sends the offer only after confirmation", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    const onCancel = vi.fn();
    render(
      <ProposeTradeDialog
        give={[player({ name: "Bench Receiver" })]}
        receive={[player({ name: "Opp RunnerOne" })]}
        pending={false}
        error={null}
        onSend={onSend}
        onCancel={onCancel}
      />,
    );

    expect(screen.getByRole("dialog", { name: "Send this offer" })).toHaveTextContent("Bench Receiver");
    expect(screen.getByRole("dialog")).toHaveTextContent("Opp RunnerOne");
    await user.click(screen.getByTestId("propose-cancel"));
    expect(onCancel).toHaveBeenCalled();
    expect(onSend).not.toHaveBeenCalled();
    await user.click(screen.getByTestId("propose-send"));
    expect(onSend).toHaveBeenCalled();
  });
});
