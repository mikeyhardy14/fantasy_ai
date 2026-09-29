import { ProposeTradeDialog } from "@/components/trades/propose-trade";
import { ToastProvider, useToast } from "@/components/shell/toast";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
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

  it("shows a toast when the offer is sent", async () => {
    const user = userEvent.setup();
    function Offer() {
      const toast = useToast();
      const [open, setOpen] = useState(true);
      if (!open) return null;
      return (
        <ProposeTradeDialog
          give={[player({ name: "Bench Receiver" })]}
          receive={[player({ name: "Opp RunnerOne" })]}
          pending={false}
          error={null}
          onCancel={() => setOpen(false)}
          onSend={() => {
            toast("Offer sent to Rival: Bench Receiver for Opp RunnerOne. They accept it in Sleeper.");
            setOpen(false);
          }}
        />
      );
    }
    render(
      <ToastProvider>
        <Offer />
      </ToastProvider>,
    );
    await user.click(screen.getByTestId("propose-send"));
    expect(await screen.findByTestId("toast")).toHaveTextContent("Offer sent to Rival");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
