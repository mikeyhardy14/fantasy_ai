import type { ReactNode } from "react";

export function PageHeader({ title, description, action, note }: { title: ReactNode; description?: ReactNode; action?: ReactNode; note?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 border-b border-white/10 pb-5 sm:mb-8 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl tracking-tight text-slate-100 sm:text-3xl">{title}</h1>
        {description ? <div className="mt-1.5 max-w-2xl text-sm leading-relaxed text-slate-400">{description}</div> : null}
        {note ? <div className="mt-1.5">{note}</div> : null}
      </div>
      {action ? <div className="flex shrink-0 items-center gap-2">{action}</div> : null}
    </div>
  );
}
