import { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it } from "vitest";
import { clearSessionDb, hydrateSessionDb, readSessionDb, writeSessionDb } from "@/lib/session-db";

describe("session database", () => {
  beforeEach(() => {
    clearSessionDb();
  });

  it("persists successful league queries for the browser session", async () => {
    const client = new QueryClient();
    await client.prefetchQuery({
      queryKey: ["leagues"],
      queryFn: async () => [{ id: "lg-1", name: "Gridiron" }],
    });
    writeSessionDb(client);

    const restored = new QueryClient();
    hydrateSessionDb(restored);
    expect(restored.getQueryData(["leagues"])).toEqual([{ id: "lg-1", name: "Gridiron" }]);
    expect(readSessionDb()?.queries.length).toBeGreaterThan(0);
  });

  it("clears on logout", async () => {
    const client = new QueryClient();
    await client.prefetchQuery({
      queryKey: ["leagues"],
      queryFn: async () => [{ id: "lg-1" }],
    });
    writeSessionDb(client);
    clearSessionDb();
    expect(readSessionDb()).toBeUndefined();
  });
});
