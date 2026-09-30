"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Brand } from "@/components/brand";
import { HeroVisual } from "@/components/landing/hero-visual";
import { Captcha, captchaEnabled } from "@/components/captcha";
import { SiteFooter } from "@/components/site-footer";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, unwrap } from "@/lib/api/client";
import { useApi } from "@/lib/api/hooks";
import { useAuth } from "@/lib/auth";
import { config } from "@/lib/config";
import { useI18n } from "@/lib/i18n";

type Mode = "login" | "signup" | "forgot";


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
  const api = useApi();

  /** Correo temporal o demasiadas cuentas desde esta conexión: se avisa antes de crear la cuenta. */
  async function signupAllowed(): Promise<boolean> {
    try {
      await unwrap(api.POST("/signup-check", { body: { email } }));
    } catch (err) {
      if (err instanceof ApiError && err.status > 0 && err.status < 500) {
        setError(err.message);
        return false;
      }
      // Si la API no responde no se bloquea el registro: la API lo vuelve a comprobar al entrar.
    }
    return true;
  }
  const router = useRouter();
  const { t } = useI18n();
  const l = t.login;
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
        setNotice(l.resetSent);
      } else if (mode === "login" || devMode) {
        await signIn(email, password, token);
      } else if (await signupAllowed()) {
        const { needsConfirmation } = await signUp(email, password, token);
        if (needsConfirmation) setNotice(l.confirmSent);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t.auth.generic);
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
      setError(err instanceof Error ? err.message : l.googleError);
    }
  }

  const [title, description, submitLabel] = l.titles[mode];
  const showGoogle = !devMode && config.googleAuth && mode !== "forgot";

  return (
    <div className="flex flex-1 flex-col">
      <main className="grid flex-1 lg:grid-cols-2">
        <div className="flex flex-col items-center justify-center gap-6 p-4 py-12">
          <Brand />
          <Card className="w-full max-w-sm shadow-sm">
            <CardHeader>
              <CardTitle>{title}</CardTitle>
              <CardDescription>{description}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              {showGoogle && (
                <>
                  <Button type="button" variant="outline" className="h-9" onClick={onGoogle}>
                    <GoogleIcon /> {l.google}
                  </Button>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground">
                    <span className="h-px flex-1 bg-border" />{l.orEmail}<span className="h-px flex-1 bg-border" />
                  </div>
                </>
              )}
              <form onSubmit={onSubmit} className="flex flex-col gap-4">
                {devMode && (
                  <Alert>
                    <AlertDescription>{l.devMode}</AlertDescription>
                  </Alert>
                )}
                <div className="flex flex-col gap-2">
                  <Label htmlFor="email">{l.email}</Label>
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
                      <Label htmlFor="password">{l.password}</Label>
                      {mode === "login" && (
                        <button
                          type="button"
                          className="text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
                          onClick={() => switchMode("forgot")}
                        >
                          {l.forgot}
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
                    {mode === "signup" && <p className="text-xs text-muted-foreground">{l.minChars}</p>}
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
                    {l.acceptStart}{" "}
                    <Link href="/legal/terminos" className="underline underline-offset-4" target="_blank">
                      {l.terms}
                    </Link>{" "}
                    {l.acceptMiddle}{" "}
                    <Link href="/legal/privacidad" className="underline underline-offset-4" target="_blank">
                      {l.privacy}
                    </Link>
                    .
                  </p>
                )}
                <Button type="submit" className="h-9" disabled={submitting || (needsCaptcha && !captchaToken)}>
                  {submitting ? l.wait : submitLabel}
                </Button>
              </form>
              {!devMode && (
                <p className="text-center text-sm text-muted-foreground">
                  {mode === "login" ? l.noAccount : mode === "signup" ? l.haveAccount : l.remember}{" "}
                  <button
                    type="button"
                    className="font-medium text-foreground underline-offset-4 hover:underline"
                    onClick={() => switchMode(mode === "login" ? "signup" : "login")}
                  >
                    {mode === "login" ? l.signUp : l.signIn}
                  </button>
                </p>
              )}
            </CardContent>
          </Card>
        </div>
        <div className="relative isolate hidden items-center justify-center overflow-hidden bg-brand-soft p-10 lg:flex">
          <div className="absolute -top-32 -right-32 -z-10 size-[28rem] rounded-full bg-primary/30 blur-3xl" />
          <div className="flex w-full max-w-lg flex-col gap-10">
            <div className="flex flex-col gap-2">
              <p className="text-3xl font-semibold tracking-tight text-balance">
                {l.asideTitleStart} <em className="text-brand-ink">{l.asideTitleAccent}</em>{l.asideTitleEnd}
              </p>
              <p className="text-muted-foreground">{l.asideLead}</p>
            </div>
            <HeroVisual />
          </div>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
