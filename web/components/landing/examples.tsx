"use client";

import { FilmIcon, TrendingUpIcon } from "lucide-react";
import { useState } from "react";

import { CaptionPreview } from "@/components/caption-preview";
import { SAMPLE_STYLES } from "@/components/landing/sample-styles";
import { Segmented } from "@/components/segmented";
import { useI18n } from "@/lib/i18n";

// Posición (en %) de los momentos elegidos dentro del vídeo original de cada ejemplo.
const MOMENTS = [
  [12, 44, 71],
  [18, 39, 83],
  [8, 52, 77],
];

/** Antes y después: un vídeo largo y los clips que saldrían de él (ilustrativo). */
export function Examples() {
  const { t } = useI18n();
  const ex = t.landing.examples;
  const [active, setActive] = useState("0");
  const i = Number(active);
  const current = ex.cases[i];

  return (
    <div className="flex flex-col gap-8">
      <Segmented
        label={ex.eyebrow}
        value={active}
        onChange={setActive}
        options={ex.cases.map((c, n) => ({ value: String(n), label: c.tab }))}
      />
      <div className="grid items-center gap-8 lg:grid-cols-[0.9fr_1.4fr]">
        <div className="flex flex-col gap-4 rounded-3xl border bg-card p-5 shadow-sm">
          <div className="flex items-center gap-2 text-sm">
            <FilmIcon className="size-4 text-muted-foreground" />
            <span className="truncate font-medium">{current.file}</span>
            <span className="ml-auto shrink-0 rounded-full bg-muted px-2 py-0.5 text-xs tabular-nums">{current.length}</span>
          </div>
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{ex.source}</p>
          {/* Forma de onda simplificada con los tramos elegidos */}
          <div className="relative flex h-20 items-center gap-[3px] overflow-hidden rounded-xl bg-muted/60 px-2">
            {Array.from({ length: 64 }, (_, k) => {
              const h = 18 + Math.abs(Math.sin(k * 1.7 + i) * 52) + ((k * 7) % 11);
              const pos = (k / 64) * 100;
              const hit = MOMENTS[i].some((m) => pos >= m && pos <= m + 8);
              return (
                <span
                  key={k}
                  className={hit ? "flex-1 rounded-full bg-primary" : "flex-1 rounded-full bg-foreground/15"}
                  style={{ height: `${Math.min(h, 90)}%` }}
                />
              );
            })}
          </div>
          <ol className="flex flex-col gap-2 text-sm">
            {current.clips.map((clip, n) => (
              <li key={clip.title} className="flex items-center gap-3">
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                  {n + 1}
                </span>
                <span className="truncate">{clip.title}</span>
              </li>
            ))}
          </ol>
        </div>

        <div className="grid grid-cols-3 gap-3 sm:gap-5">
          {current.clips.map((clip) => (
            <figure key={clip.title} className="flex flex-col gap-3">
              <div className="rounded-[1.4rem] border-4 border-slate-900 bg-slate-900 shadow-xl dark:border-slate-700">
                <CaptionPreview
                  style={SAMPLE_STYLES[current.style]}
                  words={clip.words}
                  activeIndex={1}
                  className="rounded-[1.1rem]"
                  background={
                    <div className="absolute inset-0 bg-linear-to-b from-slate-600 via-slate-800 to-slate-950">
                      <div className="absolute top-[18%] left-1/2 size-[34%] -translate-x-1/2 rounded-full bg-slate-500/70" />
                      <div className="absolute bottom-0 left-1/2 h-[42%] w-[78%] -translate-x-1/2 rounded-t-full bg-slate-600/80" />
                    </div>
                  }
                />
              </div>
              <figcaption className="flex flex-col gap-1">
                <span className="line-clamp-2 text-xs font-medium sm:text-sm">{clip.title}</span>
                <span className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span className="tabular-nums">{clip.secs} s</span>
                  <span className="flex items-center gap-1 rounded-full bg-brand-soft px-1.5 py-0.5 font-medium text-brand-ink">
                    <TrendingUpIcon className="size-3" /> {clip.score}
                  </span>
                </span>
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
      <p className="text-xs text-muted-foreground">{ex.note}</p>
    </div>
  );
}
