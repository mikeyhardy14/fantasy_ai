import { cn } from "@/lib/utils";

export function Brand({ className, mark = "h-8 w-8" }: { className?: string; mark?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-slate-100", className)}>
      <img
        src="/omaha-logo.png"
        alt=""
        width={32}
        height={32}
        fetchPriority="high"
        decoding="async"
        className={cn("rounded-md object-contain ring-1 ring-amber-400/40", mark)}
      />
      <span className="font-serif text-2xl leading-none tracking-wide">OMAHA</span>
    </span>
  );
}
