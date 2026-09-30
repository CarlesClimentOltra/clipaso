"use client";

import Link from "next/link";
import {
  AlertCircleIcon,
  AudioLinesIcon,
  AudioWaveformIcon,
  CaptionsIcon,
  ClapperboardIcon,
  ClockIcon,
  FileTextIcon,
  FilmIcon,
  FolderIcon,
  LayoutGridIcon,
  ImageIcon,
  LoaderCircleIcon,
  PlusIcon,
  RatioIcon,
  ScissorsIcon,
  SearchIcon,
  SparklesIcon,
  UploadCloudIcon,
} from "lucide-react";
import { useMemo, useState } from "react";

import { OnboardingChecklist } from "@/components/onboarding-checklist";
import { PageHeader } from "@/components/page-header";
import { Segmented } from "@/components/segmented";
import { UsageRing } from "@/components/usage-meter";
import { buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import type { JobSummary, Me } from "@/lib/api/client";
import { useJobs, useMe, usePreferences } from "@/lib/api/hooks";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { MODES, type Mode } from "@/lib/modes";
import { DeleteProjectButton } from "@/components/delete-buttons";
import { cn } from "@/lib/utils";

type Filter = "all" | "ready" | "active" | "other";

const STATUS_STYLE: Record<JobSummary["status"], string> = {
  queued: "bg-amber-100 text-amber-900 dark:bg-amber-900/60 dark:text-amber-100",
  running: "bg-amber-100 text-amber-900 dark:bg-amber-900/60 dark:text-amber-100",
  done: "bg-primary text-primary-foreground",
  failed: "bg-destructive text-white",
  expired: "bg-muted text-muted-foreground",
};

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
  const { t } = useI18n();
  const d = t.dashboard;
  const fm = t.common.minutes;
  const clips = jobs.reduce((n, j) => n + (j.status === "done" ? j.clip_count : 0), 0);
  const active = jobs.filter(isActive).length;
  return (
    <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
      <StatCard label={d.statMinutes} value={fm(Math.max(0, me.usage.remaining_minutes))}
                hint={d.statMinutesHint(fm(me.usage.used_minutes), fm(me.usage.limit_minutes))}
                icon={null}>
        <UsageRing me={me} size={44} stroke={5} />
      </StatCard>
      <StatCard icon={<FolderIcon className="size-5" />} label={d.statProjects} value={jobs.length}
                hint={active ? d.statProjectsActive(active) : d.statProjectsIdle} />
      <StatCard icon={<ScissorsIcon className="size-5" />} label={d.statClips} value={clips}
                hint={d.statClipsHint} />
      <StatCard icon={<SparklesIcon className="size-5" />} label={d.statPlan} value={t.plans[me.plan.code] ?? me.plan.name}
                hint={d.statPlanHint(me.plan.retention_days)} />
    </div>
  );
}

function ProjectCard({ job }: { job: JobSummary }) {
  const { t, formatDate } = useI18n();
  const active = isActive(job);
  const pct = Math.round(job.progress * 100);
  return (
    <div className="group/card relative">
    <Link
      href={`/projects/${job.id}`}
      className="group flex h-full flex-col overflow-hidden rounded-2xl border bg-card outline-none transition-all hover:-translate-y-0.5 hover:shadow-lg focus-visible:ring-3 focus-visible:ring-ring/50"
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
            ) : job.mode === "text" ? (
              <FileTextIcon className="size-8 text-muted-foreground" />
            ) : (
              <FilmIcon className="size-8 text-muted-foreground" />
            )}
          </div>
        )}
        <div className="absolute inset-x-0 bottom-0 h-16 bg-linear-to-t from-black/45 to-transparent" />
        <span className={cn("absolute top-3 left-3 flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium shadow-sm",
          STATUS_STYLE[job.status])}>
          {active && <span className="size-1.5 animate-pulse rounded-full bg-current" />}
          {t.dashboard.status[job.status]}
        </span>
        {job.status === "done" && (
          <span className="absolute right-3 bottom-3 flex items-center gap-1 rounded-full bg-black/55 px-2 py-0.5 text-xs text-white backdrop-blur">
            {job.mode === "thumbnail" ? (
              <><ImageIcon className="size-3" /> {t.thumbnail.badge}</>
            ) : job.mode === "subtitle" ? (
              <><CaptionsIcon className="size-3" /> {t.project.subtitledBadge(null)}</>
            ) : job.mode === "clean" ? (
              <><AudioLinesIcon className="size-3" /> {t.clean.badge}</>
            ) : job.mode === "reframe" ? (
              <><RatioIcon className="size-3" /> {t.reframe.badge}</>
            ) : job.mode === "trailer" ? (
              <><ClapperboardIcon className="size-3" /> {t.trailer.badge}</>
            ) : job.mode === "audiogram" ? (
              <><AudioWaveformIcon className="size-3" /> {t.audiogram.badge}</>
            ) : job.mode === "text" ? (
              <><FileTextIcon className="size-3" /> {t.text.badge}</>
            ) : (
              <><ScissorsIcon className="size-3" /> {job.clip_count}</>
            )}
          </span>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-1.5 p-3">
        <p className="line-clamp-1 text-sm font-medium">{job.title}</p>
        {active ? (
          <div className="flex items-center gap-3">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary transition-[width] duration-700" style={{ width: `${Math.max(pct, 4)}%` }} />
            </div>
            <span className="text-xs tabular-nums text-muted-foreground">{pct}%</span>
          </div>
        ) : (
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            {job.mode !== "thumbnail" && (
              <span className="flex items-center gap-1"><ClockIcon className="size-3.5" /> {t.common.minutes(job.video_minutes)}</span>
            )}
            <span>{formatDate(job.created_at, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</span>
            {job.status === "failed" && <span className="text-destructive">{t.dashboard.failed}</span>}
            {job.status === "expired" && <span>{t.dashboard.expired}</span>}
          </p>
        )}
      </div>
    </Link>
    {/* Borrar sin entrar al proyecto: en el ordenador aparece al pasar el ratón; en el móvil, siempre. */}
    {!active && (
      <DeleteProjectButton
        jobId={job.id}
        className="absolute right-2.5 bottom-2.5 size-8 rounded-full bg-card text-muted-foreground hover:text-destructive sm:opacity-0 sm:group-hover/card:opacity-100 sm:focus-visible:opacity-100"
      />
    )}
    </div>
  );
}

function NewProjectTile() {
  const { t } = useI18n();
  return (
    <Link
      href="/new"
      className="group flex min-h-48 flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-primary/50 bg-brand-soft/40 p-5 text-center outline-none transition-colors hover:border-primary hover:bg-brand-soft focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <span className="flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground transition-transform group-hover:scale-110">
        <PlusIcon className="size-5" />
      </span>
      <span className="font-medium">{t.dashboard.newTitle}</span>
      <span className="text-sm text-muted-foreground">{t.dashboard.newText}</span>
    </Link>
  );
}

function EmptyState() {
  const { t } = useI18n();
  return (
    <div className="relative isolate flex flex-col items-center gap-6 overflow-hidden rounded-[2rem] border bg-card px-6 py-16 text-center">
      <div className="absolute -top-20 left-1/2 -z-10 size-80 -translate-x-1/2 rounded-full bg-brand-soft blur-3xl" />
      <span className="flex size-16 items-center justify-center rounded-3xl bg-primary text-primary-foreground shadow-lg">
        <UploadCloudIcon className="size-8" />
      </span>
      <div className="flex max-w-md flex-col gap-2">
        <h2 className="text-2xl font-semibold tracking-tight">{t.dashboard.emptyTitle}</h2>
        <p className="text-muted-foreground">{t.dashboard.emptyText}</p>
      </div>
      <Link href="/new" className={cn(buttonVariants({ size: "lg" }), "h-11 rounded-full px-6 text-base")}>
        <PlusIcon /> {t.dashboard.emptyButton}
      </Link>
      <ol className="grid w-full max-w-2xl gap-3 pt-2 text-left text-sm sm:grid-cols-3">
        {t.dashboard.emptySteps.map((step, i) => (
          <li key={step} className="flex items-center gap-3 rounded-2xl bg-muted/60 p-3">
            <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-card text-xs font-semibold shadow-xs">
              {i + 1}
            </span>
            {step}
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
  const { data: prefs } = usePreferences();
  const { t } = useI18n();
  const d = t.dashboard;
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [mode, setMode] = useState<string>("all");
  // Solo los modos con algún proyecto, con cuántos hay de cada uno (en el orden de «Nuevo proyecto»).
  const modeCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const j of jobs ?? []) counts.set(j.mode ?? "clips", (counts.get(j.mode ?? "clips") ?? 0) + 1);
    return MODES.filter((m) => counts.has(m.id)).map((m) => ({ ...m, count: counts.get(m.id)! }));
  }, [jobs]);
  const name = firstName(session?.email);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (jobs ?? []).filter((j) => {
      if (q && !j.title.toLowerCase().includes(q)) return false;
      if (mode !== "all" && (j.mode ?? "clips") !== mode) return false;
      if (filter === "ready") return j.status === "done";
      if (filter === "active") return isActive(j);
      if (filter === "other") return j.status === "failed" || j.status === "expired";
      return true;
    });
  }, [jobs, query, filter, mode]);

  return (
    <div className="flex flex-col gap-10">
      <PageHeader
        eyebrow={d.eyebrow}
        title={d.hello(name)}
        description={d.lead}
      />

      {me && jobs ? (
        <Stats me={me} jobs={jobs} />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-24 rounded-3xl" />)}
        </div>
      )}

      {jobs && <OnboardingChecklist jobs={jobs} prefs={prefs} />}

      {error && <p className="text-sm text-destructive">{error.message}</p>}

      {isPending ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="aspect-4/3 rounded-3xl" />)}
        </div>
      ) : jobs && jobs.length > 0 ? (
        <section className="flex flex-col gap-5" aria-labelledby="projects-title">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="projects-title" className="scroll-mt-24 text-lg font-semibold">{d.projects}</h2>
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={d.search}
                       aria-label={d.search} className="h-9 w-52 rounded-full pl-9" />
              </div>
              <Segmented
                label={d.filterLabel}
                value={filter}
                onChange={setFilter}
                options={[
                  { value: "all", label: d.filters.all },
                  { value: "ready", label: d.filters.ready },
                  { value: "active", label: d.filters.active },
                  { value: "other", label: d.filters.other },
                ]}
              />
            </div>
          </div>
          {modeCounts.length > 1 && (
            <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:px-0" role="radiogroup"
                 aria-label={d.modeFilter}>
              {[{ id: "all", icon: LayoutGridIcon, count: jobs.length }, ...modeCounts].map((m) => {
                const selected = mode === m.id;
                return (
                  <button
                    key={m.id}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => setMode(m.id)}
                    className={cn(
                      "flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                      selected ? "border-foreground bg-foreground text-background" : "bg-card hover:bg-muted",
                    )}
                  >
                    <m.icon className="size-4" />
                    {m.id === "all" ? d.allModes : t.newProject.modes[m.id as Mode].title}
                    <span className={cn("text-xs tabular-nums", selected ? "text-background/70" : "text-muted-foreground")}>
                      {m.count}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {filter === "all" && mode === "all" && !query && <NewProjectTile />}
            {visible.map((job) => <ProjectCard key={job.id} job={job} />)}
          </div>
          {visible.length === 0 && (
            <p className="py-10 text-center text-sm text-muted-foreground">{d.noMatch}</p>
          )}
        </section>
      ) : (
        <EmptyState />
      )}
    </div>
  );
}
