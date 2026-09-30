"use client";

import Link from "next/link";
import { AudioLinesIcon, PauseIcon, PlayIcon, ScissorsIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export type TrimRange = { start: number; end: number };

/** 83.4 → «1:23.4» (con horas si hace falta). */
export function formatClock(seconds: number, tenths = true): string {
  const s = Math.max(0, seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const whole = Math.floor(sec).toString().padStart(2, "0");
  const frac = tenths ? `.${Math.floor((sec % 1) * 10)}` : "";
  return h ? `${h}:${m.toString().padStart(2, "0")}:${whole}${frac}` : `${m}:${whole}${frac}`;
}

/** «1:23», «1:23.5», «0:01:23» o «83» → segundos (null si no se entiende). */
export function parseClock(text: string): number | null {
  const parts = text.trim().replace(",", ".").split(":");
  if (!parts.length || parts.length > 3 || parts.some((p) => p === "" || isNaN(Number(p)))) return null;
  return parts.reduce((acc, p) => acc * 60 + Number(p), 0);
}

function TimeField({
  id,
  label,
  value,
  min,
  max,
  onCommit,
  onMark,
  markLabel,
  disabled,
}: {
  id: string;
  label: string;
  value: number;
  min: number;
  max: number;
  onCommit: (v: number) => void;
  onMark: () => void;
  markLabel: string;
  disabled?: boolean;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  function commit() {
    if (draft == null) return;
    const v = parseClock(draft);
    if (v != null) onCommit(Math.min(max, Math.max(min, v)));
    setDraft(null);
  }
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-xs font-medium text-muted-foreground">{label}</label>
      <div className="flex items-center gap-1.5">
        <Input
          id={id}
          value={draft ?? formatClock(value)}
          disabled={disabled}
          inputMode="decimal"
          className="h-8 w-24 font-mono tabular-nums"
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => e.key === "Enter" && commit()}
        />
        <Button type="button" size="sm" variant="ghost" onClick={onMark} disabled={disabled} className="text-xs">
          {markLabel}
        </Button>
      </div>
    </div>
  );
}

/**
 * Reproductor del vídeo elegido (en local, aún sin subir) con una barra para quedarse solo con un tramo.
 * `maxSeconds`: duración máxima que permite el plan (avisa si el tramo la supera).
 */
export function TrimSelector({
  src,
  duration,
  value,
  onChange,
  onDuration,
  maxSeconds,
  minutesFactor = 1,
  audio = false,
  disabled,
}: {
  src: string;
  duration: number | null;
  value: TrimRange | null;
  onChange: (range: TrimRange | null) => void;
  onDuration: (seconds: number, width: number, height: number) => void;
  maxSeconds: number;
  /** Los vídeos de más de 1080p cuentan el doble de minutos. */
  minutesFactor?: number;
  /** Archivo de audio (podcast): sin imagen, solo reproductor. */
  audio?: boolean;
  disabled?: boolean;
}) {
  const { t, intl } = useI18n();
  const tt = t.trim;
  const video = useRef<HTMLVideoElement>(null);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const total = duration ?? 0;
  const range = value ?? { start: 0, end: total };
  const length = range.end - range.start;
  const partial = !!value && (value.start > 0.5 || value.end < total - 0.5);
  const tooLong = total > 0 && length > maxSeconds + 0.5;
  const minutes = (Math.ceil(length / 6) / 10) * minutesFactor;

  function set(next: TrimRange) {
    const start = Math.max(0, Math.min(next.start, total - 1));
    const end = Math.min(total, Math.max(next.end, start + 1));
    onChange({ start, end });
  }

  function seek(to: number) {
    const v = video.current;
    if (v) v.currentTime = to;
    setTime(to);
  }

  // Al mover el inicio, se ve el fotograma donde empieza el tramo.
  const lastStart = useRef(range.start);
  useEffect(() => {
    if (Math.abs(lastStart.current - range.start) > 0.05) {
      lastStart.current = range.start;
      const v = video.current;
      if (v) {
        v.pause();
        v.currentTime = range.start;
      }
    }
  }, [range.start]);

  function toggle() {
    const v = video.current;
    if (!v) return;
    if (!v.paused) {
      v.pause();
      return;
    }
    if (v.currentTime < range.start || v.currentTime >= range.end - 0.1) v.currentTime = range.start;
    v.play().catch(() => {});
  }

  return (
    <div className="flex flex-col gap-4 rounded-2xl border p-4">
      <div className="flex items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-brand-soft text-brand-ink">
          <ScissorsIcon className="size-4" />
        </span>
        <div>
          <p className="text-sm font-medium">{tt.title}</p>
          <p className="text-xs text-muted-foreground">{tt.lead}</p>
        </div>
      </div>

      <div className={cn("relative overflow-hidden rounded-xl bg-black", audio && "h-28 bg-brand-ink/90")}>
        {audio && (
          <AudioLinesIcon aria-hidden="true" className="absolute top-1/2 left-1/2 size-10 -translate-1/2 text-brand" />
        )}
        <video
          ref={video}
          src={src}
          preload="metadata"
          playsInline
          className={cn("mx-auto max-h-72 w-full object-contain", audio && "hidden")}
          onLoadedMetadata={(e) => {
            const v = e.currentTarget;
            if (Number.isFinite(v.duration) && v.duration > 0) onDuration(v.duration, v.videoWidth, v.videoHeight);
          }}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onTimeUpdate={(e) => {
            const v = e.currentTarget;
            setTime(v.currentTime);
            if (!v.paused && v.currentTime >= range.end) v.pause();
          }}
        />
        <Button
          type="button"
          size="sm"
          onClick={toggle}
          disabled={!duration}
          className="absolute bottom-3 left-3 rounded-full shadow"
          aria-label={playing ? tt.pause : tt.playPart}
        >
          {playing ? <PauseIcon /> : <PlayIcon />} {playing ? tt.pause : tt.playPart}
        </Button>
        <span className="absolute right-3 bottom-3 rounded-full bg-black/60 px-2 py-1 font-mono text-xs text-white tabular-nums">
          {formatClock(time)}
        </span>
      </div>

      {duration ? (
        <>
          <div className="px-1">
            <Slider
              aria-label={tt.title}
              value={[range.start, range.end]}
              min={0}
              max={total}
              step={0.1}
              minStepsBetweenValues={10}
              disabled={disabled}
              onValueChange={(v: number | readonly number[]) => {
                if (Array.isArray(v)) set({ start: v[0], end: v[1] });
              }}
            />
            <div className="mt-1.5 flex justify-between text-[11px] text-muted-foreground tabular-nums">
              <span>0:00</span>
              <span>{formatClock(total, false)}</span>
            </div>
          </div>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div className="flex flex-wrap gap-3">
              <TimeField id="trim-start" label={tt.start} value={range.start} min={0} max={range.end - 1}
                         disabled={disabled} markLabel={tt.markHere} onMark={() => set({ ...range, start: time })}
                         onCommit={(start) => set({ ...range, start })} />
              <TimeField id="trim-end" label={tt.end} value={range.end} min={range.start + 1} max={total}
                         disabled={disabled} markLabel={tt.markHere} onMark={() => set({ ...range, end: time })}
                         onCommit={(end) => set({ ...range, end })} />
            </div>
            <div className="flex flex-col items-end gap-1 text-right">
              <span className={cn("text-sm font-medium tabular-nums", tooLong && "text-destructive")}>
                {tt.length(formatClock(length, false))}
              </span>
              <span className="text-xs text-muted-foreground">{tt.minutes(minutes.toLocaleString(intl))}</span>
              {minutesFactor > 1 && <span className="text-xs text-brand-ink">{tt.highRes}</span>}
            </div>
          </div>
          {tooLong && (
            <p className="text-sm text-destructive" role="alert">
              {tt.tooLong(Math.round(maxSeconds / 60))}{" "}
              <Link href="/plans" className="font-medium underline underline-offset-4">{t.plansPage.seePlans}</Link>
            </p>
          )}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-muted-foreground">{partial ? tt.partialNote : tt.wholeNote}</p>
            {partial && (
              <Button type="button" size="sm" variant="ghost" onClick={() => { onChange(null); seek(0); }}
                      disabled={disabled}>
                {tt.useWhole}
              </Button>
            )}
          </div>
        </>
      ) : (
        <p className="text-xs text-muted-foreground">{tt.loading}</p>
      )}
    </div>
  );
}
