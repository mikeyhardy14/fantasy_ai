import { LandingHome } from "@/components/shell/landing";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const replace = vi.fn();
const authState = vi.hoisted(() => ({
  user: null as { id: string; email: string; name: string } | null,
  loading: false,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace, refresh: vi.fn() }),
  usePathname: () => "/",
  redirect: vi.fn(),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: authState.user,
    loading: authState.loading,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
}));

describe("LandingHome", () => {
  beforeEach(() => {
    replace.mockClear();
    authState.user = null;
    authState.loading = false;
  });

  it("shows the public home for signed-out visitors", () => {
    render(<LandingHome />);
    expect(screen.getByRole("heading", { name: /rosters, matchups, and waivers/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /create an account/i })).toHaveAttribute("href", "/register");
    expect(screen.getAllByRole("link", { name: /sign in/i })[0]).toHaveAttribute("href", "/login");
    expect(replace).not.toHaveBeenCalled();
  });

  it("sends signed-in users to the dashboard", () => {
    authState.user = { id: "1", email: "a@b.co", name: "Ada" };
    render(<LandingHome />);
    expect(replace).toHaveBeenCalledWith("/dashboard");
  });
});
