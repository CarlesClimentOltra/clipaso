"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Brand } from "@/components/brand";
import { Captcha, captchaEnabled } from "@/components/captcha";
import { SiteFooter } from "@/components/site-footer";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth";
import { config } from "@/lib/config";

type Mode = "login" | "signup" | "forgot";

const TITLES: Record<Mode, { title: string; description: string; submit: string }> = {
  login: { title: "Entra en tu cuenta", description: "Bienvenido de nuevo.", submit: "Entrar" },
  signup: {
    title: "Crea tu cuenta gratis",
    description: "30 minutos de vídeo al mes gratis. Sin tarjeta.",
    submit: "Crear cuenta",
  },
  forgot: {
    title: "Recupera tu contraseña",
    description: "Te enviaremos un enlace para elegir una contraseña nueva.",
    submit: "Enviar enlace",
  },
};

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="size-4">
      <path fill="#4285F4" d="M21.6 12.2c0-.7-.1-1.4-.2-2H12v3.8h5.4a4.6 4.6 0 0 1-2 3v2.5h3.2c1.9-1.7 3-4.3 3-7.3z" />
      <path fill="#34A853" d="M12 22c2.7 0 5-.9 6.6-2.4l-3.2-2.5c-.9.6-2 1-3.4 1-2.6 0-4.8-1.8-5.6-4.1H3.1v2.6A10 10 0 0 0 12 22z" />
      <path fill="#FBBC05" d="M6.4 14c-.2-.6-.3-1.3-.3-2s.1-1.4.3-2V7.4H3.1a10 10 0 0 0 0 9.2L6.4 14z" />
      <path fill="#EA4335" d="M12 6c1.5 0 2.8.5 3.8 1.5l2.9-2.9A10 10 0 0 0 3.1 7.4L6.4 10C7.2 7.7 9.4 6 12 6z" />
    </svg>
  );
}

export default function LoginPage() {
  const { session, loading, signIn, signUp, signInWithGoogle, requestPasswordReset } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaReset, setCaptchaReset] = useState(0);
  const devMode = config.authMode === "dev";
  const needsCaptcha = !devMode && captchaEnabled();

  useEffect(() => {
    if (!loading && session) router.replace("/dashboard");
  }, [loading, session, router]);

  function switchMode(next: Mode) {
    setMode(next);
    setError(null);
    setNotice(null);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setSubmitting(true);
    const token = captchaToken ?? undefined;
    try {
      if (mode === "forgot") {
        await requestPasswordReset(email, token);
        setNotice("Si existe una cuenta con ese email, te llegará un enlace en unos minutos. Revisa también el spam.");
      } else if (mode === "login" || devMode) {
        await signIn(email, password, token);
      } else {
        const { needsConfirmation } = await signUp(email, password, token);
        if (needsConfirmation) setNotice("Te hemos enviado un email para confirmar tu cuenta. Ábrelo y vuelve a entrar.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo completar la operación.");
    } finally {
      setSubmitting(false);
      if (needsCaptcha) setCaptchaReset((n) => n + 1); // cada token sirve una sola vez
    }
  }

  async function onGoogle() {
    setError(null);
    try {
      await signInWithGoogle(); // redirige a Google y vuelve a /dashboard
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar sesión con Google.");
    }
  }

  const texts = TITLES[mode];
  const showGoogle = !devMode && config.googleAuth && mode !== "forgot";

  return (
    <div className="flex flex-1 flex-col bg-muted/30">
      <main className="flex flex-1 flex-col items-center justify-center gap-6 p-4">
        <Brand />
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>{texts.title}</CardTitle>
            <CardDescription>{texts.description}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {showGoogle && (
              <>
                <Button type="button" variant="outline" className="h-9" onClick={onGoogle}>
                  <GoogleIcon /> Continuar con Google
                </Button>
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  <span className="h-px flex-1 bg-border" />o con tu email<span className="h-px flex-1 bg-border" />
                </div>
              </>
            )}
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
              {!devMode && mode !== "forgot" && (
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="password">Contraseña</Label>
                    {mode === "login" && (
                      <button
                        type="button"
                        className="text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
                        onClick={() => switchMode("forgot")}
                      >
                        ¿La has olvidado?
                      </button>
                    )}
                  </div>
                  <Input
                    id="password"
                    type="password"
                    autoComplete={mode === "login" ? "current-password" : "new-password"}
                    required
                    minLength={mode === "signup" ? 8 : 6}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  {mode === "signup" && <p className="text-xs text-muted-foreground">Mínimo 8 caracteres.</p>}
                </div>
              )}
              {needsCaptcha && <Captcha onToken={setCaptchaToken} resetKey={captchaReset} />}
              {error && (
                <p className="text-sm text-destructive" role="alert">
                  {error}
                </p>
              )}
              {notice && (
                <p className="text-sm text-brand-ink" role="status">
                  {notice}
                </p>
              )}
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
              <Button type="submit" className="h-9" disabled={submitting || (needsCaptcha && !captchaToken)}>
                {submitting ? "Un momento…" : texts.submit}
              </Button>
            </form>
            {!devMode && (
              <p className="text-center text-sm text-muted-foreground">
                {mode === "login" ? "¿No tienes cuenta?" : mode === "signup" ? "¿Ya tienes cuenta?" : "¿La recuerdas?"}{" "}
                <button
                  type="button"
                  className="font-medium text-foreground underline-offset-4 hover:underline"
                  onClick={() => switchMode(mode === "login" ? "signup" : "login")}
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
