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
import { useI18n } from "@/lib/i18n";

function ChangeEmail() {
  const { session, updateEmail } = useAuth();
  const { t } = useI18n();
  const s = t.security;
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const next = email.trim().toLowerCase();
    if (next === session?.email.toLowerCase()) {
      setError(s.sameEmail);
      return;
    }
    setSubmitting(true);
    try {
      await updateEmail(next);
      setSentTo(next);
      setEmail("");
    } catch (err) {
      setError(err instanceof Error ? err.message : s.emailError);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3">
      <div className="flex flex-col gap-2">
        <Label htmlFor="new-email">{s.changeEmail}</Label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input
            id="new-email"
            type="email"
            autoComplete="email"
            placeholder={s.newEmailPlaceholder}
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Button type="submit" variant="outline" className="h-8 shrink-0" disabled={submitting}>
            {submitting ? s.sending : s.changeEmail}
          </Button>
        </div>
      </div>
      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}
      {sentTo && (
        <p className="text-sm text-brand-ink" role="status">
          {s.emailSentStart} <strong>{sentTo}</strong> {s.emailSentEnd}
        </p>
      )}
    </form>
  );
}

function ChangePassword() {
  const { session, signIn, updatePassword } = useAuth();
  const { t } = useI18n();
  const s = t.security;
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
      setError(s.mismatch);
      return;
    }
    setSubmitting(true);
    try {
      if (hasPassword) {
        // Confirmar la contraseña actual: así nadie puede cambiarla con una sesión abierta olvidada.
        await signIn(session!.email, current, captchaToken ?? undefined).catch(() => {
          throw new Error(s.wrongCurrent);
        });
      }
      await updatePassword(password);
      toast.success(hasPassword ? s.changed : s.created);
      setCurrent("");
      setPassword("");
      setRepeat("");
    } catch (err) {
      setError(err instanceof Error ? err.message : s.passwordError);
    } finally {
      setSubmitting(false);
      if (needsCaptcha) setCaptchaReset((n) => n + 1);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3">
      <p className="text-sm font-medium">{hasPassword ? s.changePassword : s.createPassword}</p>
      {!hasPassword && (
        <p className="text-sm text-muted-foreground">
          {s.googleOnly}
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-3">
        {hasPassword && (
          <div className="flex flex-col gap-2">
            <Label htmlFor="current-password">{s.current}</Label>
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
          <Label htmlFor="new-password">{s.newPassword}</Label>
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
          <Label htmlFor="repeat-password">{s.repeat}</Label>
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
        {submitting ? t.common.saving : hasPassword ? s.changePassword : s.createPassword}
      </Button>
    </form>
  );
}

export function AccountSecurity() {
  const { t } = useI18n();
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t.security.title}</CardTitle>
        <CardDescription>{t.security.lead}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <ChangeEmail />
        <Separator />
        <ChangePassword />
      </CardContent>
    </Card>
  );
}
