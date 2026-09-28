"use client";

import { cn } from "@/lib/utils";
import { useEffect, useRef, useState } from "react";

export function LivePoints({ value, className }: { value: string; className?: string }) {
  const seen = useRef(value);
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    if (seen.current === value) return;
    seen.current = value;
    setFlash(true);
    const timer = window.setTimeout(() => setFlash(false), 700);
    return () => window.clearTimeout(timer);
  }, [value]);

  return <span className={cn(flash && "score-flash", className)}>{value}</span>;
}

export function UpdatedAgo({ at }: { at: number }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 15_000);
    return () => window.clearInterval(timer);
  }, [at]);

  if (!at) return null;
  const age = now - at;
  if (age > 90_000) return null;
  return (
    <span className={cn("text-xs text-slate-500 transition-opacity", age > 20_000 && "opacity-50")}>Updated just now</span>
  );
}
