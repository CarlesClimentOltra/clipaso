"use client";

import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Captcha, captchaEnabled } from "@/components/captcha";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "@/lib/auth";

function ChangeEmail() {
  const { session, updateEmail } = useAuth();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const next = email.trim().toLowerCase();
    if (next === session?.email.toLowerCase()) {
      setError("Ese ya es tu email actual.");
      return;
    }
    setSubmitting(true);
    try {
      await updateEmail(next);
      setSentTo(next);
      setEmail("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cambiar el email.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3">
      <div className="flex flex-col gap-2">
        <Label htmlFor="new-email">Cambiar email</Label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input
            id="new-email"
            type="email"
            autoComplete="email"
            placeholder="nuevo@email.com"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Button type="submit" variant="outline" className="h-8 shrink-0" disabled={submitting}>
            {submitting ? "Enviando…" : "Cambiar email"}
          </Button>
        </div>
      </div>
      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}
      {sentTo && (
        <p className="text-sm text-primary" role="status">
          Te hemos enviado un enlace a <strong>{sentTo}</strong> para confirmar el cambio (y un aviso a tu email
          actual). Hasta que lo confirmes seguirás entrando con el email de siempre.
        </p>
      )}
    </form>
  );
}

function ChangePassword() {
  const { session, signIn, updatePassword } = useAuth();
  const hasPassword = session?.hasPassword ?? false;
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaReset, setCaptchaReset] = useState(0);
  const needsCaptcha = hasPassword && captchaEnabled();

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== repeat) {
      setError("Las contraseñas nuevas no coinciden.");
      return;
    }
    setSubmitting(true);
    try {
      if (hasPassword) {
        // Confirmar la contraseña actual: así nadie puede cambiarla con una sesión abierta olvidada.
        await signIn(session!.email, current, captchaToken ?? undefined).catch(() => {
          throw new Error("La contraseña actual no es correcta.");
        });
      }
      await updatePassword(password);
      toast.success(hasPassword ? "Contraseña cambiada." : "Contraseña creada: ya puedes entrar también con tu email.");
      setCurrent("");
      setPassword("");
      setRepeat("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cambiar la contraseña.");
    } finally {
      setSubmitting(false);
      if (needsCaptcha) setCaptchaReset((n) => n + 1);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3">
      <p className="text-sm font-medium">{hasPassword ? "Cambiar contraseña" : "Crear una contraseña"}</p>
      {!hasPassword && (
        <p className="text-sm text-muted-foreground">
          Entras con Google. Si quieres, crea una contraseña para poder entrar también con tu email.
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-3">
        {hasPassword && (
          <div className="flex flex-col gap-2">
            <Label htmlFor="current-password">Actual</Label>
            <Input
              id="current-password"
              type="password"
              autoComplete="current-password"
              required
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
            />
          </div>
        )}
        <div className="flex flex-col gap-2">
          <Label htmlFor="new-password">Nueva</Label>
          <Input
            id="new-password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="repeat-password">Repite la nueva</Label>
          <Input
            id="repeat-password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={repeat}
            onChange={(e) => setRepeat(e.target.value)}
          />
        </div>
      </div>
      {needsCaptcha && <Captcha onToken={setCaptchaToken} resetKey={captchaReset} />}
      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}
      <Button
        type="submit"
        variant="outline"
        className="h-8 self-start"
        disabled={submitting || (needsCaptcha && !captchaToken)}
      >
        {submitting ? "Guardando…" : hasPassword ? "Cambiar contraseña" : "Crear contraseña"}
      </Button>
    </form>
  );
}

export function AccountSecurity() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Acceso</CardTitle>
        <CardDescription>Cambia el email con el que entras o tu contraseña.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <ChangeEmail />
        <Separator />
        <ChangePassword />
      </CardContent>
    </Card>
  );
}
