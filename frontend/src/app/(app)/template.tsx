"use client";

import { cn } from "@/lib/utils";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

export default function AppTemplate({ children }: { children: ReactNode }) {
  const wide = usePathname() === "/dashboard";
  return (
    <div className={cn("page-enter mx-auto", wide ? "max-w-[100rem] px-3 py-3 sm:px-4 lg:px-5 lg:py-4" : "max-w-7xl px-4 py-8 sm:px-6 lg:px-10 lg:py-10")}>
      {children}
    </div>
  );
}
