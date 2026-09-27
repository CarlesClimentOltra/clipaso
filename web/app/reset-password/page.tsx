"use client";

// Destino del enlace de «recuperar contraseña». Supabase lee el token del enlace y abre una
// sesión temporal; aquí el usuario elige la contraseña nueva.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Brand } from "@/components/brand";
import { SiteFooter } from "@/components/site-footer";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth";

export default function ResetPasswordPage() {
  const { session, loading, updatePassword } = useAuth();
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // Enlace caducado o ya usado: Supabase vuelve con #error=… (se lee antes de que Supabase limpie la URL).
  // Mientras `loading` se muestra el esqueleto, así que el valor en el servidor no llega a pintarse.
  const [linkError] = useState(() => typeof window !== "undefined" && window.location.hash.includes("error"));

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== repeat) {
      setError("Las contraseñas no coinciden.");
      return;
    }
    setSubmitting(true);
    try {
      await updatePassword(password);
      toast.success("Contraseña cambiada. Ya has iniciado sesión.");
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cambiar la contraseña.");
    } finally {
      setSubmitting(false);
    }
  }

  let content;
  if (loading) {
    content = <Skeleton className="h-40 w-full" />;
  } else if (!session || linkError) {
    content = (
      <>
        <CardHeader>
          <CardTitle>Enlace no válido o caducado</CardTitle>
          <CardDescription>
            Los enlaces para cambiar la contraseña caducan al cabo de un tiempo y solo se pueden usar una vez. Pide uno
            nuevo.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Link href="/login" className={buttonVariants({ className: "w-full" })}>
            Volver a entrar
          </Link>
        </CardContent>
      </>
    );
  } else {
    content = (
      <>
        <CardHeader>
          <CardTitle>Elige una contraseña nueva</CardTitle>
          <CardDescription>Para la cuenta {session.email}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="password">Contraseña nueva</Label>
              <Input
                id="password"
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">Mínimo 8 caracteres.</p>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="repeat">Repite la contraseña</Label>
              <Input
                id="repeat"
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={repeat}
                onChange={(e) => setRepeat(e.target.value)}
              />
            </div>
            {error && (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            )}
            <Button type="submit" className="h-9" disabled={submitting}>
              {submitting ? "Guardando…" : "Guardar contraseña"}
            </Button>
          </form>
        </CardContent>
      </>
    );
  }

  return (
    <div className="flex flex-1 flex-col bg-muted/30">
      <main className="flex flex-1 flex-col items-center justify-center gap-6 p-4">
        <Brand />
        <Card className="w-full max-w-sm">{content}</Card>
      </main>
      <SiteFooter />
    </div>
  );
}
