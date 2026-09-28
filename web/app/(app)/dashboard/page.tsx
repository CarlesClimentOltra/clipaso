"use client";

import Link from "next/link";
import {
  AlertCircleIcon,
  ClockIcon,
  FilmIcon,
  FolderIcon,
  LoaderCircleIcon,
  PlusIcon,
  ScissorsIcon,
  SearchIcon,
  SparklesIcon,
  UploadCloudIcon,
} from "lucide-react";
import { useMemo, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Segmented } from "@/components/segmented";
import { UsageRing, formatMinutes } from "@/components/usage-meter";
import { buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import type { JobSummary, Me } from "@/lib/api/client";
import { useJobs, useMe } from "@/lib/api/hooks";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

type Filter = "all" | "ready" | "active" | "other";

const STATUS: Record<JobSummary["status"], { label: string; className: string }> = {
  queued: { label: "En cola", className: "bg-amber-100 text-amber-900 dark:bg-amber-900/60 dark:text-amber-100" },
  running: { label: "Procesando", className: "bg-amber-100 text-amber-900 dark:bg-amber-900/60 dark:text-amber-100" },
  done: { label: "Listo", className: "bg-primary text-primary-foreground" },
  failed: { label: "Error", className: "bg-destructive text-white" },
  expired: { label: "Caducado", className: "bg-muted text-muted-foreground" },
};

const dateFmt = new Intl.DateTimeFormat("es-ES", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

function isActive(job: JobSummary) {
  return job.status === "queued" || job.status === "running";
}

function firstName(email: string | undefined) {
  const local = (email ?? "").split("@")[0].split(/[._\-+0-9]/)[0];
  return local ? local.charAt(0).toUpperCase() + local.slice(1) : "";
}

function StatCard({ icon, label, value, hint, children }: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-3xl border bg-card p-4 sm:flex-row sm:items-center sm:gap-4 sm:p-5">
      {children ?? (
        <span className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-brand-soft text-brand-ink">{icon}</span>
      )}
      <div className="min-w-0">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-xl font-semibold tracking-tight tabular-nums sm:text-2xl">{value}</p>
        {hint && <p className="truncate text-xs text-muted-foreground">{hint}</p>}
      </div>
    </div>
  );
}

function Stats({ me, jobs }: { me: Me; jobs: JobSummary[] }) {
  const clips = jobs.reduce((n, j) => n + (j.status === "done" ? j.clip_count : 0), 0);
  const active = jobs.filter(isActive).length;
  return (
    <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
      <StatCard label="Minutos disponibles" value={formatMinutes(Math.max(0, me.usage.remaining_minutes))}
                hint={`${formatMinutes(me.usage.used_minutes)} de ${formatMinutes(me.usage.limit_minutes)} usados`}
                icon={null}>
        <UsageRing me={me} size={44} stroke={5} />
      </StatCard>
      <StatCard icon={<FolderIcon className="size-5" />} label="Proyectos" value={jobs.length}
                hint={active ? `${active} procesándose ahora` : "Todos al día"} />
      <StatCard icon={<ScissorsIcon className="size-5" />} label="Clips generados" value={clips}
                hint="Listos para publicar" />
      <StatCard icon={<SparklesIcon className="size-5" />} label="Tu plan" value={me.plan.name}
                hint={`Clips guardados ${me.plan.retention_days} días`} />
    </div>
  );
}

function ProjectCard({ job }: { job: JobSummary }) {
  const status = STATUS[job.status];
  const active = isActive(job);
  const pct = Math.round(job.progress * 100);
  return (
    <Link
      href={`/projects/${job.id}`}
      className="group flex flex-col overflow-hidden rounded-3xl border bg-card outline-none transition-all hover:-translate-y-0.5 hover:shadow-lg focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <div className="relative aspect-16/10 overflow-hidden bg-muted">
        {job.thumbnail_url ? (
          // eslint-disable-next-line @next/next/no-img-element -- URL firmada de almacenamiento externo
          <img src={job.thumbnail_url} alt=""
               className={cn("absolute inset-0 size-full object-cover object-[50%_22%] transition-transform duration-500 group-hover:scale-105",
                 job.status === "expired" && "grayscale")} />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center bg-linear-to-br from-slate-100 to-slate-200 dark:from-slate-800 dark:to-slate-900">
            {job.status === "failed" ? (
              <AlertCircleIcon className="size-8 text-destructive" />
            ) : active ? (
              <LoaderCircleIcon className="size-8 animate-spin text-brand-ink" />
            ) : (
              <FilmIcon className="size-8 text-muted-foreground" />
            )}
          </div>
        )}
        <div className="absolute inset-x-0 bottom-0 h-16 bg-linear-to-t from-black/45 to-transparent" />
        <span className={cn("absolute top-3 left-3 flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium shadow-sm",
          status.className)}>
          {active && <span className="size-1.5 animate-pulse rounded-full bg-current" />}
          {status.label}
        </span>
        {job.status === "done" && (
          <span className="absolute right-3 bottom-3 flex items-center gap-1 rounded-full bg-black/55 px-2 py-0.5 text-xs text-white backdrop-blur">
            <ScissorsIcon className="size-3" /> {job.clip_count}
          </span>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <p className="line-clamp-1 font-medium">{job.title}</p>
        {active ? (
          <div className="flex items-center gap-3">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary transition-[width] duration-700" style={{ width: `${Math.max(pct, 4)}%` }} />
            </div>
            <span className="text-xs tabular-nums text-muted-foreground">{pct}%</span>
          </div>
        ) : (
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span className="flex items-center gap-1"><ClockIcon className="size-3.5" /> {formatMinutes(job.video_minutes)}</span>
            <span>{dateFmt.format(new Date(job.created_at))}</span>
            {job.status === "failed" && <span className="text-destructive">No se pudo procesar</span>}
            {job.status === "expired" && <span>Clips caducados</span>}
          </p>
        )}
      </div>
    </Link>
  );
}

function NewProjectTile() {
  return (
    <Link
      href="/new"
      className="group flex min-h-64 flex-col items-center justify-center gap-3 rounded-3xl border-2 border-dashed border-primary/50 bg-brand-soft/40 p-6 text-center outline-none transition-colors hover:border-primary hover:bg-brand-soft focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <span className="flex size-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground transition-transform group-hover:scale-110">
        <PlusIcon className="size-6" />
      </span>
      <span className="font-medium">Nuevo proyecto</span>
      <span className="text-sm text-muted-foreground">Sube un vídeo y te devolvemos los mejores momentos</span>
    </Link>
  );
}

function EmptyState() {
  return (
    <div className="relative isolate flex flex-col items-center gap-6 overflow-hidden rounded-[2rem] border bg-card px-6 py-16 text-center">
      <div className="absolute -top-20 left-1/2 -z-10 size-80 -translate-x-1/2 rounded-full bg-brand-soft blur-3xl" />
      <span className="flex size-16 items-center justify-center rounded-3xl bg-primary text-primary-foreground shadow-lg">
        <UploadCloudIcon className="size-8" />
      </span>
      <div className="flex max-w-md flex-col gap-2">
        <h2 className="text-2xl font-semibold tracking-tight">Crea tus primeros clips</h2>
        <p className="text-muted-foreground">
          Sube un vídeo con diálogo (una entrevista, un podcast, una charla) y en unos minutos tendrás los mejores
          momentos en vertical, con subtítulos y texto para publicar.
        </p>
      </div>
      <Link href="/new" className={cn(buttonVariants({ size: "lg" }), "h-11 rounded-full px-6 text-base")}>
        <PlusIcon /> Subir un vídeo
      </Link>
      <ol className="grid w-full max-w-2xl gap-3 pt-2 text-left text-sm sm:grid-cols-3">
        {["Sube tu vídeo", "La IA elige los momentos", "Retoca y descarga"].map((t, i) => (
          <li key={t} className="flex items-center gap-3 rounded-2xl bg-muted/60 p-3">
            <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-card text-xs font-semibold shadow-xs">
              {i + 1}
            </span>
            {t}
          </li>
        ))}
      </ol>
    </div>
  );
}

export default function DashboardPage() {
  const { data: jobs, isPending, error } = useJobs();
  const { data: me } = useMe();
  const { session } = useAuth();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const name = firstName(session?.email);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (jobs ?? []).filter((j) => {
      if (q && !j.title.toLowerCase().includes(q)) return false;
      if (filter === "ready") return j.status === "done";
      if (filter === "active") return isActive(j);
      if (filter === "other") return j.status === "failed" || j.status === "expired";
      return true;
    });
  }, [jobs, query, filter]);

  return (
    <div className="flex flex-col gap-10">
      <PageHeader
        eyebrow="Mis proyectos"
        title={name ? `Hola, ${name}` : "Hola"}
        description="Aquí tienes tus vídeos y los clips que hemos sacado de cada uno."
      />

      {me && jobs ? (
        <Stats me={me} jobs={jobs} />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-24 rounded-3xl" />)}
        </div>
      )}

      {error && <p className="text-sm text-destructive">{error.message}</p>}

      {isPending ? (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="aspect-4/3 rounded-3xl" />)}
        </div>
      ) : jobs && jobs.length > 0 ? (
        <section className="flex flex-col gap-5" aria-labelledby="projects-title">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="projects-title" className="text-lg font-semibold">Proyectos</h2>
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar proyecto"
                       aria-label="Buscar proyecto" className="h-9 w-52 rounded-full pl-9" />
              </div>
              <Segmented
                label="Filtrar proyectos"
                value={filter}
                onChange={setFilter}
                options={[
                  { value: "all", label: "Todos" },
                  { value: "ready", label: "Listos" },
                  { value: "active", label: "En curso" },
                  { value: "other", label: "Otros" },
                ]}
              />
            </div>
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {filter === "all" && !query && <NewProjectTile />}
            {visible.map((job) => <ProjectCard key={job.id} job={job} />)}
          </div>
          {visible.length === 0 && (
            <p className="py-10 text-center text-sm text-muted-foreground">Ningún proyecto coincide con la búsqueda.</p>
          )}
        </section>
      ) : (
        <EmptyState />
      )}
    </div>
  );
}
