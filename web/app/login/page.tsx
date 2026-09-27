"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Brand } from "@/components/brand";
import { SiteFooter } from "@/components/site-footer";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth";
import { config } from "@/lib/config";

export default function LoginPage() {
  const { session, loading, signIn, signUp } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const devMode = config.authMode === "dev";

  useEffect(() => {
    if (!loading && session) router.replace("/dashboard");
  }, [loading, session, router]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setSubmitting(true);
    try {
      if (mode === "login" || devMode) {
        await signIn(email, password);
      } else {
        const { needsConfirmation } = await signUp(email, password);
        if (needsConfirmation) setNotice("Te hemos enviado un email para confirmar tu cuenta. Ábrelo y vuelve a entrar.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo completar la operación.");
    } finally {
      setSubmitting(false);
    }
  }

  const title = mode === "login" ? "Entra en tu cuenta" : "Crea tu cuenta gratis";

  return (
    <div className="flex flex-1 flex-col bg-muted/30">
      <main className="flex flex-1 flex-col items-center justify-center gap-6 p-4">
        <Brand />
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>{title}</CardTitle>
            <CardDescription>
              {mode === "signup" ? "30 minutos de vídeo al mes gratis. Sin tarjeta." : "Bienvenido de nuevo."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="flex flex-col gap-4">
              {devMode && (
                <Alert>
                  <AlertDescription>Modo desarrollo: basta con un email, sin contraseña.</AlertDescription>
                </Alert>
              )}
              <div className="flex flex-col gap-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              {!devMode && (
                <div className="flex flex-col gap-2">
                  <Label htmlFor="password">Contraseña</Label>
                  <Input
                    id="password"
                    type="password"
                    autoComplete={mode === "login" ? "current-password" : "new-password"}
                    required
                    minLength={6}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </div>
              )}
              {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
              {notice && <p className="text-sm text-primary" role="status">{notice}</p>}
              {mode === "signup" && !devMode && (
                <p className="text-xs text-muted-foreground">
                  Al crear tu cuenta aceptas los{" "}
                  <Link href="/legal/terminos" className="underline underline-offset-4" target="_blank">
                    Términos del servicio
                  </Link>{" "}
                  y confirmas que has leído la{" "}
                  <Link href="/legal/privacidad" className="underline underline-offset-4" target="_blank">
                    Política de privacidad
                  </Link>
                  .
                </p>
              )}
              <Button type="submit" className="h-9" disabled={submitting}>
                {submitting ? "Un momento…" : mode === "login" ? "Entrar" : "Crear cuenta"}
              </Button>
            </form>
            {!devMode && (
              <p className="mt-4 text-center text-sm text-muted-foreground">
                {mode === "login" ? "¿No tienes cuenta?" : "¿Ya tienes cuenta?"}{" "}
                <button
                  type="button"
                  className="font-medium text-foreground underline-offset-4 hover:underline"
                  onClick={() => {
                    setMode(mode === "login" ? "signup" : "login");
                    setError(null);
                    setNotice(null);
                  }}
                >
                  {mode === "login" ? "Regístrate" : "Inicia sesión"}
                </button>
              </p>
            )}
          </CardContent>
        </Card>
      </main>
      <SiteFooter />
    </div>
  );
}
