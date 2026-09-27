"use client";

import { MinusIcon, PlusIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { formatTime, type TimedWord } from "@/lib/captions";
import { cn } from "@/lib/utils";

export const MIN_CLIP = 3;
export const MAX_CLIP = 180;

function Nudge({ label, onMinus, onPlus }: { label: string; onMinus: () => void; onPlus: () => void }) {
  return (
    <div className="flex items-center gap-1">
      <Button type="button" variant="outline" size="icon-sm" onClick={onMinus} aria-label={`${label}: medio segundo antes`}>
        <MinusIcon />
      </Button>
      <Button type="button" variant="outline" size="icon-sm" onClick={onPlus} aria-label={`${label}: medio segundo después`}>
        <PlusIcon />
      </Button>
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
}: {
  min: number;
  max: number;
  start: number;
  end: number;
  words: TimedWord[];
  onChange: (start: number, end: number) => void;
  disabled?: boolean;
}) {
  const set = (s: number, e: number) => {
    s = Math.max(min, Math.min(s, max - MIN_CLIP));
    e = Math.min(max, Math.max(e, s + MIN_CLIP));
    if (e - s > MAX_CLIP) e = s + MAX_CLIP;
    onChange(Math.round(s * 10) / 10, Math.round(e * 10) / 10);
  };
  const duration = end - start;

  function pickWord(w: TimedWord) {
    // Una palabra antes de la mitad del clip marca el inicio; después, el final.
    if (w.start < (start + end) / 2) set(w.start - 0.1, end);
    else set(start, w.end + 0.25);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between text-sm">
        <span className="tabular-nums">
          <span className="text-muted-foreground">Inicio</span> {formatTime(start, true)}
        </span>
        <span className="rounded-md bg-muted px-2 py-0.5 text-xs font-medium tabular-nums">
          {duration.toFixed(1)} s
        </span>
        <span className="tabular-nums">
          <span className="text-muted-foreground">Fin</span> {formatTime(end, true)}
        </span>
      </div>
      <Slider
        min={min}
        max={max}
        step={0.1}
        minStepsBetweenValues={MIN_CLIP * 10}
        value={[start, end]}
        disabled={disabled}
        aria-label="Recorte del clip"
        onValueChange={(v: number | readonly number[]) => Array.isArray(v) && set(v[0], v[1])}
      />
      <div className="flex items-center justify-between">
        <Nudge label="Inicio" onMinus={() => set(start - 0.5, end)} onPlus={() => set(start + 0.5, end)} />
        <span className="text-xs text-muted-foreground">
          {formatTime(min)} – {formatTime(max)} del vídeo original
        </span>
        <Nudge label="Fin" onMinus={() => set(start, end - 0.5)} onPlus={() => set(start, end + 0.5)} />
      </div>
      {duration > 60 && (
        <p className="text-xs text-amber-600 dark:text-amber-400">
          Más de 60 s: TikTok y Reels lo aceptan, pero los Shorts de YouTube se cortan al minuto.
        </p>
      )}
      <div className="flex flex-col gap-2">
        <p className="text-xs text-muted-foreground">
          Toca una palabra para que el clip empiece o termine ahí. Las atenuadas quedan fuera.
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
