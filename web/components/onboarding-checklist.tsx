"use client";

import Link from "next/link";
import { ArrowRightIcon, CheckIcon, XIcon } from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import type { JobSummary, Preferences } from "@/lib/api/client";
import { useFlag } from "@/lib/flags";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export const ONBOARDING_FLAGS = {
  dismissed: "onboarding.dismissed",
  styled: "onboarding.styled",
  reviewed: "onboarding.reviewed",
} as const;

/** Primeros pasos para usuarios nuevos: se marcan solos y desaparecen al completarlos o al ocultarlos. */
export function OnboardingChecklist({ jobs, prefs }: { jobs: JobSummary[]; prefs?: Preferences }) {
  const { t } = useI18n();
  const [dismissed, dismiss] = useFlag(ONBOARDING_FLAGS.dismissed);
  const [styled] = useFlag(ONBOARDING_FLAGS.styled);
  const [reviewed] = useFlag(ONBOARDING_FLAGS.reviewed);

  const done = [
    styled || !!prefs?.branding.handle || !!prefs?.branding.has_logo,
    jobs.length > 0,
    reviewed && jobs.some((j) => j.status === "done"),
  ];
  const hrefs = ["/customize", "/new", "/dashboard#projects-title"];
  const completed = done.filter(Boolean).length;
  if (dismissed || completed === done.length) return null;

  return (
    <section
      aria-labelledby="onboarding-title"
      className="relative isolate overflow-hidden rounded-[2rem] border bg-card p-6 sm:p-8"
    >
      <div className="absolute -top-24 -right-20 -z-10 size-72 rounded-full bg-brand-soft blur-3xl" />
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h2 id="onboarding-title" className="text-xl font-semibold tracking-tight">{t.onboarding.title}</h2>
          <p className="text-sm text-muted-foreground">{t.onboarding.lead}</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium tabular-nums text-brand-ink">{completed}/{done.length}</span>
          <Button variant="ghost" size="icon-sm" aria-label={t.onboarding.dismiss} onClick={dismiss}>
            <XIcon />
          </Button>
        </div>
      </div>
      <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary transition-[width] duration-700"
             style={{ width: `${(completed / done.length) * 100}%` }} />
      </div>
      <ol className="mt-6 grid gap-3 md:grid-cols-3">
        {t.onboarding.steps.map(([title, text, action], i) => (
          <li
            key={title}
            className={cn("flex flex-col gap-3 rounded-2xl border p-4", done[i] ? "border-primary/40 bg-brand-soft/60" : "bg-card")}
          >
            <div className="flex items-center gap-3">
              <span className={cn(
                "flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                done[i] ? "bg-primary text-primary-foreground" : "border bg-card",
              )}>
                {done[i] ? <CheckIcon className="size-4" /> : i + 1}
              </span>
              <span className={cn("font-medium", done[i] && "text-muted-foreground line-through")}>{title}</span>
            </div>
            <p className="text-sm text-muted-foreground">{text}</p>
            {done[i] ? (
              <span className="mt-auto text-xs font-medium text-brand-ink">{t.onboarding.done}</span>
            ) : (
              <Link href={hrefs[i]} className={cn(buttonVariants({ variant: "outline", size: "sm" }), "mt-auto self-start rounded-full")}>
                {action} <ArrowRightIcon />
              </Link>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
