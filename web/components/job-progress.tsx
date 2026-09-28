"use client";

import { CheckIcon, LoaderCircleIcon } from "lucide-react";

import { Progress } from "@/components/ui/progress";
import type { Job } from "@/lib/api/client";
import { cn } from "@/lib/utils";

// Etapas visibles para el usuario (agrupan las etapas internas del pipeline).
const STEPS = [
  { key: "prepare", label: "Preparando el vídeo", stages: ["queued", "starting", "ingest", "audio"] },
  { key: "transcribe", label: "Transcribiendo el audio", stages: ["transcribe"] },
  { key: "analyze", label: "Buscando los mejores momentos", stages: ["signals", "select"] },
  { key: "render", label: "Generando tus clips", stages: ["export", "preview"] },
] as const;

function stepIndex(stage: string | null | undefined): number {
  const i = STEPS.findIndex((s) => (s.stages as readonly string[]).includes(stage ?? ""));
  return i === -1 ? 0 : i;
}

export function JobProgress({ job }: { job: Job }) {
  const current = stepIndex(job.stage);
  const pct = Math.round((job.progress ?? 0) * 100);
  const queued = job.status === "queued";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="text-sm text-muted-foreground">Estamos preparando tus clips</p>
            <p className="text-xl font-semibold tracking-tight">{queued ? "En cola, empezamos enseguida…" : STEPS[current].label}</p>
          </div>
          <span className="text-4xl font-semibold tracking-tight tabular-nums">{pct}%</span>
        </div>
        <Progress value={pct} aria-label="Progreso del procesamiento" className="h-2.5" />
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
              {step.label}
            </li>
          );
        })}
      </ol>
      <p className="text-sm text-muted-foreground">
        Puedes cerrar esta página: seguiremos trabajando y tus clips aparecerán en <strong>Mis proyectos</strong>.
        Suele tardar unos minutos por cada hora de vídeo.
      </p>
    </div>
  );
}
