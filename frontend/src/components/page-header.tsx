import type { ReactNode } from "react";

export function PageHeader({ title, description, action, note }: { title: ReactNode; description?: ReactNode; action?: ReactNode; note?: ReactNode }) {
  return (
    <div className="mb-6 flex items-start justify-between gap-3 border-b border-surface-border pb-5 sm:mb-8 sm:items-end">
      <div className="min-w-0">
        <h1 className="text-3xl text-slate-100 sm:text-4xl">{title}</h1>
        {description ? <div className="mt-2 hidden max-w-2xl text-sm leading-relaxed text-slate-400 sm:block">{description}</div> : null}
        {note ? <div className="mt-1">{note}</div> : null}
      </div>
      {action ? <div className="flex shrink-0 items-center gap-2">{action}</div> : null}
    </div>
  );
}
