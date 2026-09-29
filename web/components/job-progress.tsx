"use client";

import { CheckIcon, LoaderCircleIcon } from "lucide-react";

import { Progress } from "@/components/ui/progress";
import type { Job } from "@/lib/api/client";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

// Etapas visibles para el usuario (agrupan las etapas internas del pipeline).
const STEPS = [
  { key: "prepare", stages: ["queued", "starting", "ingest", "audio"] },
  { key: "transcribe", stages: ["transcribe"] },
  { key: "analyze", stages: ["cut", "signals", "select", "translate", "write"] },
  { key: "render", stages: ["export", "preview"] },
] as const;

function stepIndex(stage: string | null | undefined): number {
  const i = STEPS.findIndex((s) => (s.stages as readonly string[]).includes(stage ?? ""));
  return i === -1 ? 0 : i;
}

export function JobProgress({ job }: { job: Job }) {
  const current = stepIndex(job.stage);
  const pct = Math.round((job.progress ?? 0) * 100);
  const queued = job.status === "queued";
  const { t } = useI18n();
  // Modos de vídeo entero con sus propios pasos (sin silencios, cambiar formato).
  const whole = ({ clean: t.clean, reframe: t.reframe, trailer: t.trailer, audiogram: t.audiogram,
                   text: t.text } as Record<string, { badge: string; title: string; preparing: string;
                                                      steps: readonly string[] }>)[job.options.mode ?? ""] ?? null;
  const subtitle = job.options.mode === "subtitle" || !!whole;
  const labels = whole
    ? whole.steps
    : subtitle ? t.progress.subtitleSteps(!!job.options.subtitle_language) : t.progress.steps;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="text-sm text-muted-foreground">{whole ? whole.preparing : subtitle ? t.progress.preparingSubtitle : t.progress.preparing}</p>
            <p className="text-xl font-semibold tracking-tight">{queued ? t.progress.queued : labels[current]}</p>
          </div>
          <span className="text-4xl font-semibold tracking-tight tabular-nums">{pct}%</span>
        </div>
        <Progress value={pct} aria-label={t.progress.label} className="h-2.5" />
      </div>
      <ol className="grid gap-3 sm:grid-cols-4">
        {STEPS.map((step, i) => {
          const done = i < current;
          const active = i === current && !queued;
          return (
            <li
              key={step.key}
              className={cn(
                "flex items-center gap-2 rounded-2xl border bg-card/70 p-3 text-sm transition-colors",
                done && "border-primary/40 bg-brand-soft",
                active && "border-primary ring-2 ring-primary/30",
                !done && !active && "text-muted-foreground",
              )}
            >
              <span
                className={cn(
                  "flex size-6 shrink-0 items-center justify-center rounded-full border text-xs",
                  done && "border-primary bg-primary text-primary-foreground",
                  active && "border-primary text-brand-ink",
                )}
              >
                {done ? <CheckIcon className="size-3.5" /> : active ? <LoaderCircleIcon className="size-3.5 animate-spin" /> : i + 1}
              </span>
              {labels[i]}
            </li>
          );
        })}
      </ol>
      <p className="text-sm text-muted-foreground">
        {t.progress.leave} <strong>{t.progress.leaveLink}</strong>
        {t.progress.leaveEnd}
      </p>
    </div>
  );
}
