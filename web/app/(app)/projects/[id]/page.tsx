"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";
import {
  ArrowLeftIcon,
  CalendarClockIcon,
  ClapperboardIcon,
  ClockIcon,
  FolderDownIcon,
  ImageIcon,
  Loader2Icon,
  RotateCcwIcon,
  ScissorsIcon,
  SmartphoneIcon,
  Trash2Icon,
} from "lucide-react";
import { toast } from "sonner";

import { CleanSummary } from "@/components/clean-summary";
import { formatTime } from "@/lib/captions";
import { ClipCard } from "@/components/clip-card";
import { CoverEditor } from "@/components/editor/cover-editor";
import { JobProgress } from "@/components/job-progress";
import { TextResults } from "@/components/text-results";
import { MoreClipsDialog } from "@/components/more-clips-dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { useDeleteJob, useDownloadAll, useJob, useMe } from "@/lib/api/hooks";
import { ONBOARDING_FLAGS } from "@/components/onboarding-checklist";
import { setFlag } from "@/lib/flags";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";


export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: job, error, isPending } = useJob(id);
  const { data: me } = useMe();
  const remove = useDeleteJob();
  const downloadAll = useDownloadAll(id);
  const { t, formatDate } = useI18n();
  const p = t.project;
  const longDate = (d: string) => formatDate(d, { day: "numeric", month: "long" });

  // Ver los clips completa el último paso de «Primeros pasos».
  useEffect(() => {
    if (job?.status === "done" && job.clips.length > 0) setFlag(ONBOARDING_FLAGS.reviewed);
  }, [job?.status, job?.clips.length]);

  if (isPending) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-8 w-72" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }
  if (error || !job) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <Alert variant="destructive">
        <AlertTitle>{notFound ? p.notFound : p.loadError}</AlertTitle>
        <AlertDescription>
          {notFound ? p.notFoundText : error?.message}{" "}
          <Link href="/dashboard" className="underline">{p.backLink}</Link>
        </AlertDescription>
      </Alert>
    );
  }

  const active = job.status === "queued" || job.status === "running";
  const clean = job.options.mode === "clean";
  // Textos propios de los modos de vídeo entero con nombre propio (sin silencios, cambiar formato).
  const whole = ({ clean: t.clean, reframe: t.reframe, trailer: t.trailer, audiogram: t.audiogram,
                   text: t.text } as Record<string, { badge: string; title: string; preparing: string;
                                                      steps: readonly string[] }>)[job.options.mode ?? ""] ?? null;
  const text = job.options.mode === "text";
  // El resultado es el vídeo entero (subtitulado, sin silencios o en otro formato), no varios clips.
  const subtitle = job.options.mode === "subtitle" || !!whole;
  const thumbnail = job.options.mode === "thumbnail";
  const moreTask = job.more_clips_task;
  const searchingMore = !!moreTask && (moreTask.status === "queued" || moreTask.status === "running");

  async function onDownloadAll() {
    try {
      await downloadAll.mutateAsync();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : p.downloadError);
    }
  }

  async function onDelete() {
    try {
      await remove.mutateAsync(job!.id);
      toast.success(p.deleted);
      router.replace("/dashboard");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : p.deleteError);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-4">
        <Link href="/dashboard" className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "-ml-2 self-start rounded-full")}>
          <ArrowLeftIcon /> {p.back}
        </Link>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex min-w-0 flex-col gap-3">
            <span className="text-sm font-medium text-brand-ink">{p.eyebrow}</span>
            <h1 className="truncate text-3xl font-semibold tracking-tight">{job.title}</h1>
            <div className="flex flex-wrap gap-2 text-xs">
              {thumbnail ? (
                <span className="flex items-center gap-1.5 rounded-full border bg-card px-3 py-1">
                  <ImageIcon className="size-3.5 text-brand-ink" /> {t.thumbnail.badge}
                </span>
              ) : (
                <>
                  <span className="flex items-center gap-1.5 rounded-full border bg-card px-3 py-1">
                    <ClockIcon className="size-3.5 text-brand-ink" /> {p.ofVideo(t.common.minutes(job.video_minutes))}
                  </span>
                  {!text && (
                    <span className="flex items-center gap-1.5 rounded-full border bg-card px-3 py-1">
                      <SmartphoneIcon className="size-3.5 text-brand-ink" />
                      {t.options.formats[job.options.format ?? "vertical"]?.[0]}
                    </span>
                  )}
                </>
              )}
              {job.status === "done" && !thumbnail && (
                <span className="flex items-center gap-1.5 rounded-full border bg-card px-3 py-1">
                  <ScissorsIcon className="size-3.5 text-brand-ink" />
                  {whole
                    ? whole.badge
                    : subtitle ? p.subtitledBadge(job.options.subtitle_language) : t.common.clips(job.clips.length)}
                </span>
              )}
              {job.status === "done" && job.expires_at && (
                <span className="flex items-center gap-1.5 rounded-full border bg-card px-3 py-1">
                  <CalendarClockIcon className="size-3.5 text-brand-ink" /> {p.availableUntil(longDate(job.expires_at))}
                </span>
              )}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {job.status === "done" && job.clips.length > 0 && !subtitle && !thumbnail && (
              <Button size="sm" className="h-9 rounded-full px-4" onClick={onDownloadAll} disabled={downloadAll.isPending}>
                <FolderDownIcon /> {p.downloadAll}
              </Button>
            )}
            {job.status === "done" && job.can_edit && me && !subtitle && (
              <MoreClipsDialog job={job} maxPerRequest={me.plan.max_clips_per_job} />
            )}
            {!active && (
              <Dialog>
                <DialogTrigger render={<Button variant="outline" size="sm" className="h-9 rounded-full px-4" />}>
                  <Trash2Icon /> {p.delete}
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>{p.deleteTitle}</DialogTitle>
                    <DialogDescription>
                      {p.deleteText}
                    </DialogDescription>
                  </DialogHeader>
                  <DialogFooter>
                    <DialogClose render={<Button variant="outline" />}>{t.common.cancel}</DialogClose>
                    <Button variant="destructive" onClick={onDelete} disabled={remove.isPending}>
                      {p.deleteConfirm}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            )}
          </div>
        </div>
      </div>

      {active && (
        <div className="relative isolate overflow-hidden rounded-[2rem] border bg-card p-6 sm:p-8">
          <div className="absolute -top-24 -right-16 -z-10 size-72 rounded-full bg-brand-soft blur-3xl" />
          <JobProgress job={job} />
        </div>
      )}

      {job.status === "failed" && (
        <Alert variant="destructive">
          <AlertTitle>{p.failedTitle}</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-3">
            <span>{job.error_message}</span>
            <Link href="/new" className={buttonVariants({ variant: "outline", size: "sm" })}>
              <RotateCcwIcon /> {p.tryAnother}
            </Link>
          </AlertDescription>
        </Alert>
      )}

      {job.status === "expired" && (
        <Alert>
          <AlertTitle>{p.expiredTitle}</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-3">
            <span>{p.expiredText(job.expires_at ? longDate(job.expires_at) : null)}</span>
            <Link href="/new" className={buttonVariants({ variant: "outline", size: "sm" })}>
              <RotateCcwIcon /> {p.newProject}
            </Link>
          </AlertDescription>
        </Alert>
      )}

      {searchingMore && (
        <Alert>
          <Loader2Icon className="animate-spin" />
          <AlertTitle>{p.searchingTitle}</AlertTitle>
          <AlertDescription>{p.searchingText}</AlertDescription>
        </Alert>
      )}
      {moreTask?.status === "failed" && moreTask.error_message && (
        <Alert>
          <AlertTitle>{p.noNewClips}</AlertTitle>
          <AlertDescription>{moreTask.error_message}</AlertDescription>
        </Alert>
      )}
      {job.status === "done" && !job.can_edit && !thumbnail && !text && (
        <p className="text-sm text-muted-foreground">
          {p.notEditable}
        </p>
      )}

      {job.status === "done" && thumbnail && job.clips[0]?.cover && (
        <section className="rounded-[2rem] border bg-card p-5 sm:p-8" aria-label={t.thumbnail.badge}>
          <CoverEditor clip={job.clips[0]} jobId={job.id} previewUrl={null} canChangeFrame={false} large />
        </section>
      )}

      {job.status === "done" && clean && job.clean_stats && <CleanSummary stats={job.clean_stats} />}
      {job.status === "done" && job.trailer_stats && (
        <p className="flex items-center gap-2 rounded-2xl border bg-card px-4 py-3 text-sm" aria-label={t.trailer.summaryLabel}>
          <ClapperboardIcon className="size-4 shrink-0 text-brand-ink" />
          {t.trailer.summary(job.trailer_stats.moments, formatTime(job.trailer_stats.original_seconds),
                             formatTime(job.trailer_stats.trailer_seconds))}
        </p>
      )}

      {job.status === "done" && text && job.text_results && <TextResults job={job} />}

      {job.status === "done" && !thumbnail && !text && (
        <section className="flex flex-col gap-4" aria-labelledby="clips-title">
          <h2 id="clips-title" className="text-xl font-semibold tracking-tight">
            {whole ? whole.title : subtitle ? p.subtitledTitle : p.clipsTitle(job.clips.length)}
          </h2>
          <div className={cn("grid gap-5", subtitle
            ? job.frame === "horizontal" ? "max-w-3xl" : "max-w-sm"
            : "sm:grid-cols-2 lg:grid-cols-3")}>
            {job.clips.map((clip) => (
              <ClipCard key={clip.id} clip={clip} job={job} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
