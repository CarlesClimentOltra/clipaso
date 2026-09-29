"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";
import { ArrowLeftIcon, ClockIcon, GiftIcon, LightbulbIcon } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { ThumbnailForm } from "@/components/thumbnail-form";
import { UploadForm } from "@/components/upload-form";
import { UsageRing } from "@/components/usage-meter";
import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useMe } from "@/lib/api/hooks";
import { useI18n } from "@/lib/i18n";
import { findMode } from "@/lib/modes";
import { cn } from "@/lib/utils";

/** Configuración y subida de un modo concreto (se llega desde «Nuevo proyecto»). */
export default function NewModePage() {
  const params = useParams<{ mode: string }>();
  const mode = findMode(params.mode);
  const router = useRouter();
  const { data: me, error } = useMe();
  const { t } = useI18n();
  const n = t.newProject;

  useEffect(() => {
    if (!mode) router.replace("/new");
  }, [mode, router]);
  if (!mode) return null;
  const m = n.modes[mode.id];

  return (
    <div className="flex flex-col gap-8">
      <Link href="/new" className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "-ml-2 self-start rounded-full")}>
        <ArrowLeftIcon /> {n.changeMode}
      </Link>
      <PageHeader
        eyebrow={n.eyebrow}
        title={
          <span className="flex items-center gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <mode.icon className="size-5" />
            </span>
            {m.title}
          </span>
        }
        description={m.lead}
      />
      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        <div className="rounded-[2rem] border bg-card p-5 shadow-sm sm:p-8">
          {mode.id === "thumbnail" ? (
            <ThumbnailForm />
          ) : error ? (
            <p className="text-sm text-destructive">{error.message}</p>
          ) : me ? (
            <UploadForm me={me} mode={mode.id} />
          ) : (
            <Skeleton className="h-96 w-full rounded-3xl" />
          )}
        </div>
        <aside className="flex flex-col gap-4 lg:sticky lg:top-24 lg:self-start">
          {mode.usesMinutes ? (
            me && (
              <div className="flex items-center gap-4 rounded-3xl border bg-card p-5">
                <UsageRing me={me} size={48} stroke={5} />
                <div>
                  <p className="text-sm text-muted-foreground">{n.left}</p>
                  <p className="text-xl font-semibold tabular-nums">
                    {t.common.minutes(Math.max(0, me.usage.remaining_minutes))}
                  </p>
                  <p className="flex items-center gap-1 text-xs text-muted-foreground">
                    <ClockIcon className="size-3" /> {n.maxVideo(me.plan.max_video_minutes)}
                  </p>
                </div>
              </div>
            )
          ) : (
            <div className="flex items-center gap-3 rounded-3xl border bg-card p-5 text-sm">
              <GiftIcon className="size-5 shrink-0 text-brand-ink" /> {n.free}
            </div>
          )}
          <div className="flex flex-col gap-4 rounded-3xl bg-slate-950 p-5 text-white">
            <p className="flex items-center gap-2 text-sm font-medium text-lime-300">
              <LightbulbIcon className="size-4" /> {n.tipsTitle}
            </p>
            <ul className="flex flex-col gap-4">
              {m.tips.map(([title, text]) => (
                <li key={title}>
                  <span className="block text-sm font-medium">{title}</span>
                  <span className="block text-xs text-white/65">{text}</span>
                </li>
              ))}
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
}
