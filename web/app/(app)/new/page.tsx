"use client";

import Link from "next/link";
import { ArrowLeftIcon, CaptionsIcon, ClockIcon, MailIcon, MicIcon, MonitorPlayIcon } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { UploadForm } from "@/components/upload-form";
import { UsageRing, formatMinutes } from "@/components/usage-meter";
import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useMe } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";

const TIPS = [
  { icon: MicIcon, title: "Con conversación", text: "Entrevistas, podcasts, charlas o directos. La IA elige por lo que se dice." },
  { icon: MonitorPlayIcon, title: "Mejor en 1080p", text: "Suben mucho más rápido que en 4K y los clips se ven igual de bien." },
  { icon: CaptionsIcon, title: "Audio claro", text: "Cuanto mejor se oiga, más precisos serán los subtítulos." },
  { icon: MailIcon, title: "Puedes irte", text: "Te avisamos por email cuando tus clips estén listos." },
];

export default function NewProjectPage() {
  const { data: me, error } = useMe();

  return (
    <div className="flex flex-col gap-8">
      <Link href="/dashboard" className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "-ml-2 self-start rounded-full")}>
        <ArrowLeftIcon /> Mis proyectos
      </Link>
      <PageHeader
        eyebrow="Nuevo proyecto"
        title="Convierte un vídeo en clips"
        description="Súbelo, elige cómo quieres los clips y nosotros encontramos los momentos con más gancho."
      />
      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        <div className="rounded-[2rem] border bg-card p-5 shadow-sm sm:p-8">
          {error ? (
            <p className="text-sm text-destructive">{error.message}</p>
          ) : me ? (
            <UploadForm me={me} />
          ) : (
            <Skeleton className="h-96 w-full rounded-3xl" />
          )}
        </div>
        <aside className="flex flex-col gap-4 lg:sticky lg:top-24 lg:self-start">
          {me && (
            <div className="flex items-center gap-4 rounded-3xl border bg-card p-5">
              <UsageRing me={me} size={48} stroke={5} />
              <div>
                <p className="text-sm text-muted-foreground">Te quedan este mes</p>
                <p className="text-xl font-semibold tabular-nums">{formatMinutes(Math.max(0, me.usage.remaining_minutes))}</p>
                <p className="flex items-center gap-1 text-xs text-muted-foreground">
                  <ClockIcon className="size-3" /> Vídeos de hasta {me.plan.max_video_minutes} min
                </p>
              </div>
            </div>
          )}
          <div className="flex flex-col gap-4 rounded-3xl bg-slate-950 p-5 text-white">
            <p className="text-sm font-medium text-lime-300">Consejos para mejores clips</p>
            <ul className="flex flex-col gap-4">
              {TIPS.map(({ icon: Icon, title, text }) => (
                <li key={title} className="flex gap-3">
                  <Icon className="mt-0.5 size-4 shrink-0 text-lime-300" />
                  <span>
                    <span className="block text-sm font-medium">{title}</span>
                    <span className="block text-xs text-white/65">{text}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
}
