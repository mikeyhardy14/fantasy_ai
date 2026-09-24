"use client";

import { useAuth } from "@/lib/auth";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button } from "./ui/button";
import { Input, Label } from "./ui/input";
import { InlineError } from "./ui/states";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const { login, register } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, name, password);
      router.push("/dashboard");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[minmax(0,32rem)_1fr]">
      <div className="px-6 py-12 sm:px-12 sm:py-16">
        <p className="font-serif text-2xl text-slate-100">Fantasy</p>
        <h1 className="mt-12 text-4xl text-slate-100">{mode === "login" ? "Sign in" : "Create an account"}</h1>
        <p className="mt-3 max-w-sm text-sm leading-relaxed text-slate-400">
          {mode === "login"
            ? "This signs you into the leagues already imported here. Sleeper is connected separately, by username."
            : "An account here holds your imported leagues. It is not your Sleeper login."}
        </p>
        <form onSubmit={onSubmit} className="mt-8 max-w-sm space-y-4 border-t border-surface-border pt-6">
          {mode === "register" ? (
            <div>
              <Label htmlFor="name">Name</Label>
              <Input id="name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} autoComplete="name" />
            </div>
          ) : null}
          <div>
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
            {mode === "register" ? <p className="mt-1 text-[11px] text-slate-500">At least 8 characters.</p> : null}
          </div>
          <InlineError error={error} />
          <Button type="submit" loading={busy}>
            {mode === "login" ? "Sign in" : "Create account"}
          </Button>
        </form>
        <p className="mt-6 text-sm text-slate-400">
          {mode === "login" ? (
            <>
              No account yet?{" "}
              <Link href="/register" className="text-brand hover:underline">
                Register
              </Link>
            </>
          ) : (
            <>
              Already registered?{" "}
              <Link href="/login" className="text-brand hover:underline">
                Sign in
              </Link>
            </>
          )}
        </p>
      </div>
      <aside className="hidden border-l border-surface-border bg-surface-raised px-12 py-16 lg:block">
        <p className="font-serif text-3xl text-slate-100">What you can do after signing in</p>
        <ol className="mt-8 max-w-sm space-y-5 text-sm leading-relaxed text-slate-300">
          <li>
            <span className="font-medium text-slate-100">1. Import a league.</span> Sleeper needs the username, not the password.
          </li>
          <li>
            <span className="font-medium text-slate-100">2. Paste the Sleeper token</span> from the web app if you want lineup edits. It stays encrypted on the server.
          </li>
          <li>
            <span className="font-medium text-slate-100">3. Open Multi-Box</span> to see every imported team, its host, and a link to the league.
          </li>
        </ol>
      </aside>
    </div>
  );
}