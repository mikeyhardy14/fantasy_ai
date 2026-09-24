"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, tokenStore } from "./api";
import type { TokenResponse, User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, name: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const queryClient = useQueryClient();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!tokenStore.get()) {
        setLoading(false);
        return;
      }
      try {
        const me = await api.auth.me();
        if (!cancelled) setUser(me);
      } catch {
        tokenStore.clear();
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const applyToken = useCallback((resp: TokenResponse) => {
    tokenStore.set(resp.access_token);
    setUser(resp.user);
  }, []);

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
    queryClient.clear();
    router.push("/login");
  }, [queryClient, router]);

  useEffect(() => {
    const handler = () => {
      setUser(null);
      queryClient.clear();
      router.push("/login");
    };
    window.addEventListener("fantasy-ai:unauthorized", handler);
    return () => window.removeEventListener("fantasy-ai:unauthorized", handler);
  }, [queryClient, router]);

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      login: async (email, password) => applyToken(await api.auth.login({ email, password })),
      register: async (email, name, password) => applyToken(await api.auth.register({ email, name, password })),
      logout,
    }),
    [user, loading, applyToken, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
