"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { ApiError } from "@/lib/api/client";
import { useLocaleSync, useMe } from "@/lib/api/hooks";

import { AppHeader } from "@/components/app-header";
import { SiteFooter } from "@/components/site-footer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

// La API no crea la cuenta (correo temporal o demasiadas cuentas gratis desde la misma conexión).
const BLOCKED = new Set(["email_disposable", "too_many_accounts"]);

export function AppShell({ children }: { children: ReactNode }) {
  const { session, loading, signOut } = useAuth();
  useLocaleSync();
  const router = useRouter();
  const { error } = useMe();
  const { t } = useI18n();

  useEffect(() => {
    if (!loading && !session) router.replace("/login");
  }, [loading, session, router]);

  if (loading || !session) {
    return (
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 p-4 pt-20">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (error instanceof ApiError && BLOCKED.has(error.code)) {
    return (
      <div className="mx-auto flex w-full max-w-md flex-1 items-center p-4">
        <Card className="w-full">
          <CardHeader>
            <CardTitle>{t.plansPage.blockedTitle}</CardTitle>
            <CardDescription>{error.message}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              className="w-full"
              onClick={async () => {
                await signOut();
                router.replace("/login");
              }}
            >
              {t.header.signOut}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="relative isolate flex flex-1 flex-col">
      {/* Halo lima arriba a la derecha, como en la portada */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-105 bg-[radial-gradient(60%_100%_at_85%_0%,var(--color-brand-soft),transparent)]"
      />
      <AppHeader />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10">{children}</main>
      <SiteFooter />
    </div>
  );
}
