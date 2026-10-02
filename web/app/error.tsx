"use client";

import Link from "next/link";
import { useEffect } from "react";

import { StatusPage } from "@/components/status-page";
import { Button, buttonVariants } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n";

/** Error inesperado al pintar una página: mensaje claro y opción de reintentar (sin perder la sesión). */
export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const { t } = useI18n();
  const s = t.status;
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <StatusPage code=":(" title={s.errorTitle} text={s.errorText}>
      <Button onClick={reset}>{s.retry}</Button>
      <Link href="/dashboard" className={buttonVariants({ variant: "outline" })}>{s.projects}</Link>
    </StatusPage>
  );
}
