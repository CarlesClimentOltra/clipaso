"use client";

import { FilmIcon, PlayIcon, SparklesIcon, TrendingUpIcon } from "lucide-react";
import { useEffect, useState } from "react";

import { CaptionPreview } from "@/components/caption-preview";
import type { CaptionStyle } from "@/lib/api/client";
import { captionStyle } from "@/components/landing/sample-styles";
import { useI18n } from "@/lib/i18n";

const STYLE: CaptionStyle = captionStyle({ highlight_color: "B6E34A" });
// Fragmentos elegidos por la IA dentro del vídeo largo (en % de su duración).
const HIGHLIGHTS = [
  { left: 9, width: 7 },
  { left: 31, width: 9 },
  { left: 58, width: 6 },
  { left: 79, width: 8 },
];

/** Escena abstracta de alguien hablando a cámara (sin fotos de terceros). */
function SpeakerScene() {
  return (
    <div className="absolute inset-0 overflow-hidden bg-linear-to-b from-slate-700 via-slate-800 to-slate-950">
      <div className="absolute -top-10 left-1/2 size-56 -translate-x-1/2 rounded-full bg-lime-200/25 blur-3xl" />
      <svg viewBox="0 0 100 178" className="absolute bottom-0 left-1/2 h-[92%] w-auto -translate-x-1/2" aria-hidden="true">
        <defs>
          <linearGradient id="hv-body" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#64748b" />
            <stop offset="1" stopColor="#1e293b" />
          </linearGradient>
        </defs>
        <circle cx="50" cy="78" r="17" fill="url(#hv-body)" />
        <path d="M14 178c2-40 16-62 36-62s34 22 36 62z" fill="url(#hv-body)" />
      </svg>
    </div>
  );
}

function Donut({ value }: { value: number }) {
  const r = 26;
  const c = 2 * Math.PI * r;
  return (
    <svg viewBox="0 0 64 64" className="size-16 -rotate-90" aria-hidden="true">
      <circle cx="32" cy="32" r={r} fill="none" className="stroke-muted" strokeWidth="8" />
      <circle cx="32" cy="32" r={r} fill="none" className="stroke-primary" strokeWidth="8" strokeLinecap="round"
              strokeDasharray={`${(value / 100) * c} ${c}`} />
    </svg>
  );
}

export function HeroVisual() {
  const [tick, setTick] = useState(0);
  const { t } = useI18n();
  const h = t.landing.hero;

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = setInterval(() => setTick((t) => t + 1), 520);
    return () => clearInterval(id);
  }, []);

  const line = h.lines[Math.floor(tick / 3) % h.lines.length];

  return (
    <div className="relative mx-auto aspect-[1/1.02] w-full max-w-[560px]" aria-hidden="true">
      {/* Halo de color detrás de la composición */}
      <div className="absolute -inset-10 -z-10 rounded-full bg-[radial-gradient(closest-side,var(--color-brand-soft),transparent)]" />

      {/* Vídeo largo con los momentos elegidos */}
      <div className="absolute top-[16%] left-0 w-[58%] rounded-2xl border bg-card p-3 shadow-xl">
        <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
          <FilmIcon className="size-3.5" />
          <span className="truncate">{h.file}</span>
          <span className="ml-auto tabular-nums">48:12</span>
        </div>
        <div className="relative aspect-video overflow-hidden rounded-lg">
          <SpeakerScene />
          <span className="absolute inset-0 m-auto flex size-10 items-center justify-center rounded-full bg-white/90 text-slate-900">
            <PlayIcon className="size-4 translate-x-px fill-current" />
          </span>
        </div>
        <div className="relative mt-3 h-2 rounded-full bg-muted">
          {HIGHLIGHTS.map((h, i) => (
            <span key={i} className="absolute inset-y-0 rounded-full bg-primary"
                  style={{ left: `${h.left}%`, width: `${h.width}%` }} />
          ))}
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">{h.moments}</span> {h.withPotential}
        </p>
      </div>

      {/* El clip resultante en un móvil */}
      <div className="absolute top-0 right-[2%] w-[42%] rounded-[2rem] border-[6px] border-slate-900 bg-slate-900 shadow-2xl">
        <CaptionPreview
          style={STYLE}
          words={line}
          activeIndex={tick % 3}
          branding={{ handle: h.handle, position: "top-left", enabled: true }}
          background={<SpeakerScene />}
          className="rounded-[1.6rem]"
        />
      </div>

      {/* Tarjetas flotantes */}
      <div className="float-soft absolute top-[2%] left-[6%] flex items-center gap-2 rounded-full border bg-card/95 px-4 py-2.5 text-sm shadow-lg backdrop-blur">
        <SparklesIcon className="size-4 text-brand-ink" />
        <span className="text-muted-foreground">{h.ask} <span className="text-foreground">{h.askTopic}</span></span>
      </div>

      <div className="absolute bottom-[6%] left-[4%] flex items-center gap-3 rounded-2xl border bg-card p-3 pr-5 shadow-xl">
        <div className="relative">
          <Donut value={92} />
          <span className="absolute inset-0 flex items-center justify-center text-sm font-semibold">92</span>
        </div>
        <div className="text-sm">
          <p className="font-medium">{h.viral}</p>
          <p className="text-xs text-muted-foreground">{h.viralClip}</p>
        </div>
      </div>

      <div className="float-soft absolute right-0 bottom-[2%] w-[46%] rounded-2xl border bg-card p-4 shadow-xl [animation-delay:-3s]">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{h.monthClips}</span>
          <span className="flex items-center gap-1 rounded-md bg-brand-soft px-1.5 py-0.5 font-medium text-brand-ink">
            <TrendingUpIcon className="size-3" /> 32%
          </span>
        </div>
        <p className="mt-1 text-2xl font-semibold tabular-nums">48</p>
        <svg viewBox="0 0 120 32" className="mt-2 h-8 w-full" preserveAspectRatio="none">
          <path d="M0 26 L15 22 L30 24 L45 16 L60 18 L75 10 L90 13 L105 6 L120 4" fill="none"
                className="stroke-brand-ink" strokeWidth="2" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
        </svg>
      </div>
    </div>
  );
}
