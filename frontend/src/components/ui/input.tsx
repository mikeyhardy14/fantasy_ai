import { cn } from "@/lib/utils";
import { forwardRef, type InputHTMLAttributes, type SelectHTMLAttributes } from "react";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      className={cn(
        "h-9 w-full rounded-lg border border-surface-border bg-surface px-3 text-sm text-slate-100 transition-colors placeholder:text-slate-500 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand",
        className,
      )}
      {...props}
    />
  );
});

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "h-9 rounded-lg border border-surface-border bg-surface px-3 text-sm text-slate-100 transition-colors focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand",
        className,
      )}
      {...props}
    />
  );
}

export function Label({ children, htmlFor }: { children: React.ReactNode; htmlFor?: string }) {
  return (
    <label htmlFor={htmlFor} className="mb-1.5 block text-xs font-medium text-slate-400">
      {children}
    </label>
  );
}
