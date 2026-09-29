"use client";

import Link from "next/link";
import { ArrowLeftIcon, ArrowRightIcon, CheckIcon, ClockIcon, GiftIcon } from "lucide-react";

import { ModeArt } from "@/components/mode-art";
import { PageHeader } from "@/components/page-header";
import { UsageRing } from "@/components/usage-meter";
import { buttonVariants } from "@/components/ui/button";
import { useMe } from "@/lib/api/hooks";
import { useI18n } from "@/lib/i18n";
import { MODES } from "@/lib/modes";
import { cn } from "@/lib/utils";

/** «Nuevo proyecto»: lo primero es elegir qué hacer con el vídeo; cada modo tiene su propia pantalla. */
export default function NewProjectPage() {
  const { data: me } = useMe();
  const { t } = useI18n();
  const n = t.newProject;

  return (
    <div className="flex flex-col gap-8">
      <Link href="/dashboard" className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "-ml-2 self-start rounded-full")}>
        <ArrowLeftIcon /> {n.back}
      </Link>
      <PageHeader
        eyebrow={n.eyebrow}
        title={n.title}
        description={n.lead}
        actions={me && (
          <div className="flex items-center gap-3 rounded-full border bg-card py-1.5 pr-4 pl-1.5">
            <UsageRing me={me} size={34} stroke={4} />
            <div className="leading-tight">
              <p className="text-sm font-semibold tabular-nums">{t.common.minutes(Math.max(0, me.usage.remaining_minutes))}</p>
              <p className="text-xs text-muted-foreground">{n.left}</p>
            </div>
          </div>
        )}
      />

      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {MODES.map((mode) => {
          const m = n.modes[mode.id];
          return (
            <Link
              key={mode.id}
              href={`/new/${mode.id}`}
              className="group flex flex-col overflow-hidden rounded-[1.75rem] border bg-card shadow-sm transition-all outline-none hover:-translate-y-0.5 hover:border-primary hover:shadow-md focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              <ModeArt mode={mode.id} className="h-40" />
              <div className="flex flex-1 flex-col gap-4 p-5 sm:p-6">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground">
                      <mode.icon className="size-5" />
                    </span>
                    <h2 className="text-lg font-semibold tracking-tight">{m.title}</h2>
                  </div>
                  {mode.isNew && (
                    <span className="shrink-0 rounded-full bg-brand-soft px-2.5 py-0.5 text-xs font-medium text-brand-ink">
                      {n.isNew}
                    </span>
                  )}
                </div>
                <p className="text-sm text-muted-foreground">{m.card}</p>
                <div className="flex flex-col gap-2">
                  <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{n.youGet}</span>
                  <ul className="flex flex-col gap-1.5">
                    {m.gets.map((g) => (
                      <li key={g} className="flex items-start gap-2 text-sm">
                        <CheckIcon className="mt-0.5 size-4 shrink-0 text-brand-ink" /> {g}
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="mt-auto flex flex-wrap items-center justify-between gap-3 border-t pt-4">
                  <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    {mode.usesMinutes ? <ClockIcon className="size-3.5" /> : <GiftIcon className="size-3.5 text-brand-ink" />}
                    {mode.usesMinutes ? n.usesMinutes : n.free}
                  </span>
                  <span className={cn(buttonVariants({ size: "sm" }), "rounded-full px-4 group-hover:gap-2.5")}>
                    {n.start} <ArrowRightIcon />
                  </span>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
