"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useLocaleSync } from "@/lib/api/hooks";

import { AppHeader } from "@/components/app-header";
import { SiteFooter } from "@/components/site-footer";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth";

export function AppShell({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth();
  useLocaleSync();
  const router = useRouter();

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
