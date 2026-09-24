"use client";

import { api } from "@/lib/api";
import { useLeague } from "@/lib/league";
import { useHealth } from "@/lib/queries";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Button } from "./ui/button";
import { Card, CardBody } from "./ui/card";
import { EmptyState, InlineError } from "./ui/states";

export function NoLeague() {
  const router = useRouter();
  const { refetch, select } = useLeague();
  const health = useHealth();
  const demo = useMutation({
    mutationFn: api.demo.createLeague,
    onSuccess: (league) => {
      refetch();
      select(league.id);
      router.push("/dashboard");
    },
  });

  return (
    <Card className="mx-auto max-w-xl">
      <CardBody>
        <EmptyState
          title="No league connected yet"
          description="Connect your Sleeper account to import a real league, or load the demo league to explore every feature with sample data."
          action={
            <div className="flex flex-col items-center gap-3">
              <div className="flex flex-wrap justify-center gap-2">
                <Button onClick={() => router.push("/connect/sleeper")}>Connect Sleeper</Button>
                {health.data?.demo_enabled !== false ? (
                  <Button variant="secondary" onClick={() => demo.mutate()} loading={demo.isPending}>
                    Load demo league
                  </Button>
                ) : null}
              </div>
              <InlineError error={demo.error} />
            </div>
          }
        />
      </CardBody>
    </Card>
  );
}
