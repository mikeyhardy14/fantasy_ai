"use client";

import { cn } from "@/lib/utils";
import { createContext, useContext } from "react";

export const SheetContext = createContext<((playerId: string) => void) | null>(null);

export function PlayerName({
  id,
  name,
  className,
}: {
  id: string;
  name: string;
  className?: string;
}) {
  const open = useContext(SheetContext);
  if (!open) return <span className={className}>{name}</span>;
  return (
    <button
      type="button"
      className={cn(className, "text-left hover:underline")}
      onClick={(event) => {
        event.stopPropagation();
        open(id);
      }}
    >
      {name}
    </button>
  );
}
