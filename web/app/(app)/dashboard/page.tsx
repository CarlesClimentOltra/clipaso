"use client";

import Link from "next/link";
import { AlertCircleIcon, FilmIcon, PlusIcon } from "lucide-react";

import { formatMinutes } from "@/components/usage-meter";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import type { JobSummary } from "@/lib/api/client";
import { useJobs, useMe } from "@/lib/api/hooks";

const STATUS: Record<JobSummary["status"], { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  queued: { label: "En cola", variant: "outline" },
  running: { label: "Procesando", variant: "secondary" },
  done: { label: "Listo", variant: "default" },
  failed: { label: "Error", variant: "destructive" },
};

const dateFmt = new Intl.DateTimeFormat("es-ES", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

function ProjectCard({ job }: { job: JobSummary }) {
  const status = STATUS[job.status];
  const active = job.status === "queued" || job.status === "running";
  return (
    <Link href={`/projects/${job.id}`} className="group rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-ring/50">
      <Card className="h-full overflow-hidden pt-0 transition-shadow group-hover:shadow-md">
        <div className="relative flex aspect-video items-center justify-center overflow-hidden bg-muted">
          {job.thumbnail_url ? (
            // eslint-disable-next-line @next/next/no-img-element -- URL firmada de almacenamiento externo
            <img src={job.thumbnail_url} alt="" className="absolute inset-0 size-full object-cover object-[50%_22%]" />
          ) : job.status === "failed" ? (
            <AlertCircleIcon className="size-8 text-destructive" />
          ) : (
            <FilmIcon className="size-8 text-muted-foreground" />
          )}
          <Badge variant={status.variant} className="absolute top-2 left-2">
            {status.label}
          </Badge>
        </div>
        <CardContent className="flex flex-col gap-2">
          <p className="line-clamp-1 font-medium">{job.title}</p>
          {active ? (
            <Progress value={Math.round(job.progress * 100)} aria-label={`Progreso de ${job.title}`} />
          ) : (
            <p className="text-xs text-muted-foreground">
              {job.status === "done" ? `${job.clip_count} ${job.clip_count === 1 ? "clip" : "clips"}` : "No se pudo procesar"} · {formatMinutes(job.video_minutes)} ·{" "}
              {dateFmt.format(new Date(job.created_at))}
            </p>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}

export default function DashboardPage() {
  const { data: jobs, isPending, error } = useJobs();
  const { data: me } = useMe();

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Mis proyectos</h1>
          {me && (
            <p className="text-sm text-muted-foreground">
              Plan {me.plan.name} · te quedan {formatMinutes(me.usage.remaining_minutes)} este mes
            </p>
          )}
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error.message}</p>}

      {isPending ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="aspect-[4/3] rounded-xl" />
          ))}
        </div>
      ) : jobs && jobs.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {jobs.map((job) => (
            <ProjectCard key={job.id} job={job} />
          ))}
        </div>
      ) : (
        <Card className="items-center gap-4 py-16 text-center">
          <FilmIcon className="size-10 text-muted-foreground" />
          <div>
            <p className="font-medium">Todavía no tienes proyectos</p>
            <p className="text-sm text-muted-foreground">Sube tu primer vídeo y te devolvemos los mejores momentos listos para publicar.</p>
          </div>
          <Link href="/new" className={buttonVariants()}>
            <PlusIcon /> Crear mi primer proyecto
          </Link>
        </Card>
      )}
    </div>
  );
}
