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
        "h-10 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-sm text-slate-100 transition-colors placeholder:text-slate-500 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/40",
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
        "h-10 cursor-pointer rounded-lg border border-white/10 bg-surface-overlay px-3 text-sm text-slate-100 transition-colors focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/40",
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
