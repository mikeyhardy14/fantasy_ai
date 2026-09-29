import { AuthForm } from "@/components/shell/auth-form";
import { notFound } from "next/navigation";

export default async function AuthPage({ params }: { params: Promise<{ mode: string }> }) {
  const { mode } = await params;
  if (mode !== "login" && mode !== "register") notFound();
  return <AuthForm mode={mode} />;
}
