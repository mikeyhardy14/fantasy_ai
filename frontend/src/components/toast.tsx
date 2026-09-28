"use client";

import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

const ToastContext = createContext<(message: string) => void>(() => {});

export function useToast() {
  return useContext(ToastContext);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<{ id: number; message: string }[]>([]);

  const push = useCallback((message: string) => {
    const id = Date.now() + Math.random();
    setToasts((current) => [...current, { id, message }]);
    window.setTimeout(() => {
      setToasts((current) => current.filter((item) => item.id !== id));
    }, 4000);
  }, []);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[60] flex flex-col items-center gap-2 px-4">
        {toasts.map((item) => (
          <p
            key={item.id}
            data-testid="toast"
            role="status"
            className="sheet-enter pointer-events-auto max-w-md rounded-lg border border-surface-border bg-surface-raised px-4 py-2 text-sm text-slate-100 shadow-card"
          >
            {item.message}
          </p>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
