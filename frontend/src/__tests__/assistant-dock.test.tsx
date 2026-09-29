import { AssistantDock } from "@/components/chat/assistant-dock";
import { ToastProvider } from "@/components/shell/toast";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

function renderDock() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <AssistantDock leagueId="league-1" aiEnabled />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("Assistant dock", () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true, status: 200, text: async () => "[]" })),
    );
  });

  it("opens, enlarges, and minimizes the assistant", async () => {
    const user = userEvent.setup();
    renderDock();
    expect(screen.getByTestId("assistant-dock")).toHaveAttribute("data-size", "closed");
    await user.click(screen.getByRole("button", { name: "Assistant" }));
    expect(screen.getByTestId("assistant-dock")).toHaveAttribute("data-size", "small");
    expect(screen.getByLabelText("Message")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Enlarge assistant" }));
    expect(screen.getByTestId("assistant-dock")).toHaveAttribute("data-size", "large");
    await user.click(screen.getByRole("button", { name: "Minimize assistant" }));
    expect(screen.getByTestId("assistant-dock")).toHaveAttribute("data-size", "closed");
  });
});
