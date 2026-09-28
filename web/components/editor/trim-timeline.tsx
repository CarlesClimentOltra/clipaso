"use client";

import { MinusIcon, PlusIcon } from "lucide-react";
import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { formatTime, type TimedWord } from "@/lib/captions";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export const MIN_CLIP = 3;
export const MAX_CLIP = 180;

function Nudge({ label, onMinus, onPlus }: { label: string; onMinus: () => void; onPlus: () => void }) {
  const { t } = useI18n();
  return (
    <div className="flex items-center gap-1">
      <Button type="button" variant="outline" size="icon-sm" onClick={onMinus} aria-label={t.editor.trim.earlier(label)}>
        <MinusIcon />
      </Button>
      <Button type="button" variant="outline" size="icon-sm" onClick={onPlus} aria-label={t.editor.trim.later(label)}>
        <PlusIcon />
      </Button>
    </div>
  );
}

const FRAMES = 12;

/**
 * Miniaturas del vídeo a lo largo de la ventana del editor. Se dibujan en canvas desde un <video> oculto
 * (sirve aunque el vídeo esté en otro dominio: solo se pinta, no se leen los píxeles).
 */
function Filmstrip({ src, min, max }: { src: string; min: number; max: number }) {
  const canvases = useRef<(HTMLCanvasElement | null)[]>([]);

  useEffect(() => {
    let cancelled = false;
    const video = document.createElement("video");
    video.muted = true;
    video.playsInline = true;
    video.preload = "auto";
    video.src = src;
    const wait = (event: string, ms: number) =>
      new Promise<void>((resolve) => {
        const timer = window.setTimeout(resolve, ms);
        video.addEventListener(event, () => {
          window.clearTimeout(timer);
          resolve();
        }, { once: true });
      });
    (async () => {
      await wait("loadeddata", 15000);
      for (let i = 0; i < FRAMES && !cancelled; i++) {
        const seeked = wait("seeked", 3000);
        video.currentTime = min + ((max - min) * (i + 0.5)) / FRAMES;
        await seeked;
        const canvas = canvases.current[i];
        const ctx = canvas?.getContext("2d");
        if (!canvas || !ctx || !video.videoWidth) continue;
        const scale = Math.max(canvas.width / video.videoWidth, canvas.height / video.videoHeight);
        const w = video.videoWidth * scale;
        const h = video.videoHeight * scale;
        ctx.drawImage(video, (canvas.width - w) / 2, (canvas.height - h) / 2, w, h);
      }
    })();
    return () => {
      cancelled = true;
      video.removeAttribute("src");
      video.load();
    };
  }, [src, min, max]);

  return (
    <div className="absolute inset-0 flex">
      {Array.from({ length: FRAMES }, (_, i) => (
        <canvas
          key={i}
          ref={(el) => {
            canvases.current[i] = el;
          }}
          width={90}
          height={160}
          className="h-full min-w-0 flex-1 border-r border-black/20 object-cover last:border-r-0"
        />
      ))}
    </div>
  );
}

/** Recorte del clip: barra con inicio y fin, ajuste fino y palabras para cortar justo donde quieras. */
export function TrimTimeline({
  min,
  max,
  start,
  end,
  words,
  onChange,
  disabled,
  previewUrl,
  energy = [],
  energyStep = 0.5,
}: {
  min: number;
  max: number;
  start: number;
  end: number;
  words: TimedWord[];
  onChange: (start: number, end: number) => void;
  disabled?: boolean;
  /** Vídeo ligero del original para las miniaturas. */
  previewUrl?: string | null;
  /** Volumen del audio (0-1) cada `energyStep` segundos desde `min`. */
  energy?: number[];
  energyStep?: number;
}) {
  const { t } = useI18n();
  const tt = t.editor.trim;
  const set = (s: number, e: number) => {
    s = Math.max(min, Math.min(s, max - MIN_CLIP));
    e = Math.min(max, Math.max(e, s + MIN_CLIP));
    if (e - s > MAX_CLIP) e = s + MAX_CLIP;
    onChange(Math.round(s * 10) / 10, Math.round(e * 10) / 10);
  };
  const duration = end - start;
  const span = Math.max(0.1, max - min);
  const pct = (t: number) => `${((Math.min(max, Math.max(min, t)) - min) / span) * 100}%`;

  function pickWord(w: TimedWord) {
    // Una palabra antes de la mitad del clip marca el inicio; después, el final.
    if (w.start < (start + end) / 2) set(w.start - 0.1, end);
    else set(start, w.end + 0.25);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between text-sm">
        <span className="tabular-nums">
          <span className="text-muted-foreground">{tt.start}</span> {formatTime(start, true)}
        </span>
        <span className="rounded-md bg-muted px-2 py-0.5 text-xs font-medium tabular-nums">
          {duration.toFixed(1)} s
        </span>
        <span className="tabular-nums">
          <span className="text-muted-foreground">{tt.end}</span> {formatTime(end, true)}
        </span>
      </div>
      <div className="relative h-20 overflow-hidden rounded-xl bg-muted select-none" aria-hidden="true">
        {previewUrl && <Filmstrip src={previewUrl} min={min} max={max} />}
        {energy.length > 0 && (
          <div className="absolute inset-x-0 bottom-0 flex h-2/5 items-end gap-px">
            {energy.map((v, i) => {
              const at = min + i * energyStep;
              const inside = at >= start && at <= end;
              return (
                <span
                  key={i}
                  className={cn("min-w-px flex-1 rounded-t-[1px]", inside ? "bg-primary/75" : "bg-white/45")}
                  style={{ height: `${Math.max(6, v * 100)}%` }}
                />
              );
            })}
          </div>
        )}
        <div className="absolute inset-y-0 left-0 bg-background/70" style={{ width: pct(start) }} />
        <div className="absolute inset-y-0 right-0 bg-background/70" style={{ left: pct(end) }} />
        <div className="absolute inset-y-0 rounded-lg border-2 border-primary shadow-[0_0_0_1px_rgba(0,0,0,.15)]"
             style={{ left: pct(start), right: `calc(100% - ${pct(end)})` }} />
      </div>
      <Slider
        min={min}
        max={max}
        step={0.1}
        minStepsBetweenValues={MIN_CLIP * 10}
        value={[start, end]}
        disabled={disabled}
        aria-label={tt.label}
        onValueChange={(v: number | readonly number[]) => Array.isArray(v) && set(v[0], v[1])}
      />
      <div className="flex items-center justify-between">
        <Nudge label={tt.start} onMinus={() => set(start - 0.5, end)} onPlus={() => set(start + 0.5, end)} />
        <span className="text-xs text-muted-foreground">
          {formatTime(min)} – {formatTime(max)} {tt.ofOriginal}
        </span>
        <Nudge label={tt.end} onMinus={() => set(start, end - 0.5)} onPlus={() => set(start, end + 0.5)} />
      </div>
      {duration > 60 && (
        <p className="text-xs text-amber-600 dark:text-amber-400">
          {tt.longWarning}
        </p>
      )}
      <div className="flex flex-col gap-2">
        <p className="text-xs text-muted-foreground">
          {tt.wordsHint}
        </p>
        <div className="max-h-56 overflow-y-auto rounded-lg border p-3 text-sm leading-7">
          {words.map((w) => {
            const inside = w.start >= start - 0.01 && w.end <= end + 0.01;
            return (
              <button
                key={w.key}
                type="button"
                disabled={disabled}
                onClick={() => pickWord(w)}
                title={formatTime(w.start, true)}
                className={cn(
                  "rounded px-0.5 hover:bg-primary/15",
                  inside ? "text-foreground" : "text-muted-foreground/60",
                )}
              >
                {w.text}{" "}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
