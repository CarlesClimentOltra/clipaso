"use client";

import Link from "next/link";
import { toast } from "sonner";

import { buttonVariants } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { dictionary } from "@/lib/i18n";

// Errores que se resuelven con otro plan: el aviso lleva a la página de planes.
const PLAN_ERRORS = new Set(["daily_limit", "plan_required", "quota_exceeded", "too_many_thumbnails", "upload_too_large"]);

export function PlansLink({ className }: { className?: string }) {
  return (
    <Link href="/plans" className={buttonVariants({ size: "sm", variant: "outline", className })}>
      {dictionary().plansPage.seePlans}
    </Link>
  );
}

/** Muestra el error de la API (o `fallback`); si es un límite del plan, con el enlace «Ver planes». */
export function toastError(err: unknown, fallback: string) {
  if (!(err instanceof ApiError)) {
    toast.error(fallback);
    return;
  }
  if (PLAN_ERRORS.has(err.code)) toast.error(err.message, { action: <PlansLink className="ml-auto" /> });
  else toast.error(err.message);
}
