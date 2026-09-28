"use client";

import { useEffect, useState, type CSSProperties } from "react";

import type { BrandingPrefs, CaptionStyle } from "@/lib/api/client";
import { captionFontFamily, captionFontVariables } from "@/lib/caption-fonts";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export type ClipFormat = "vertical" | "square" | "horizontal";

// Mismas proporciones que los perfiles del motor (configs/output_profiles).
const FRAME: Record<ClipFormat, { aspect: string; size: number; margin: number }> = {
  vertical: { aspect: "9 / 16", size: 0.045, margin: 0.28 },
  square: { aspect: "1 / 1", size: 0.05, margin: 0.12 },
  horizontal: { aspect: "16 / 9", size: 0.06, margin: 0.09 },
};
const WORD_MS = 420;

type Props = {
  style: CaptionStyle;
  format?: ClipFormat;
  /** Palabras fijas (editor). Sin ellas se usa una frase de ejemplo. */
  words?: string[];
  activeIndex?: number;
  /** Recorre la frase de ejemplo palabra a palabra, como en el clip. */
  animate?: boolean;
  branding?: Pick<BrandingPrefs, "handle" | "position" | "enabled"> | null;
  logoUrl?: string | null;
  background?: React.ReactNode;
  className?: string;
};

function hexAlpha(hex: string, opacity: number) {
  const a = Math.round((Math.max(0, Math.min(100, opacity)) / 100) * 255);
  return `#${hex}${a.toString(16).padStart(2, "0")}`;
}

/** Palabra activa que avanza sola mientras `enabled`. */
function useTicker(length: number, enabled: boolean) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!enabled || length <= 0) return;
    const id = window.setInterval(() => setTick((t) => t + 1), WORD_MS);
    return () => window.clearInterval(id);
  }, [enabled, length]);
  return length > 0 ? tick % length : 0;
}

/** Vista previa de cómo quedarán los subtítulos (y la marca) en el clip: mismos tamaños que el render. */
export function CaptionPreview({
  style,
  format = "vertical",
  words,
  activeIndex = 1,
  animate = false,
  branding,
  logoUrl,
  background,
  className,
}: Props) {
  const { t } = useI18n();
  const sample = t.styles.sample;
  const perLine = Math.max(1, style.max_words ?? 3);
  const tick = useTicker(sample.length, animate && !words);

  let shown: string[];
  let active: number;
  if (words) {
    shown = words;
    active = activeIndex;
  } else if (animate) {
    const start = Math.floor(tick / perLine) * perLine;
    shown = sample.slice(start, start + perLine);
    active = tick - start;
  } else {
    shown = sample.slice(0, Math.min(perLine, 3));
    // Miniatura fija: en «aparecer» se ven ya todas las palabras (si no, la frase quedaría a medias).
    active = style.animation === "appear" ? shown.length - 1 : Math.min(activeIndex, shown.length - 1);
  }

  const frame = FRAME[format];
  // Unidades relativas al alto del marco (container queries), como en el render real.
  const ratio = frame.size * ((style.scale ?? 100) / 100);
  const outlineEm = (style.outline ?? 4) / 1000 / ratio;
  const shadowEm = (style.shadow ?? 2) / 1000 / ratio;
  const box = !!style.box;
  const text: CSSProperties = {
    fontFamily: captionFontFamily(style.font ?? "Archivo Black"),
    fontSize: `${ratio * 100}cqh`,
    color: `#${style.text_color}`,
    textTransform: style.uppercase ? "uppercase" : "none",
    lineHeight: 1.2,
    // El contorno del motor crece hacia fuera; con paint-order solo se ve la mitad exterior del trazo.
    WebkitTextStroke: !box && outlineEm > 0 ? `${outlineEm * 2}em #${style.outline_color ?? "000000"}` : undefined,
    paintOrder: "stroke fill",
    textShadow: !box && shadowEm > 0 ? `${shadowEm}em ${shadowEm}em 0 rgba(0,0,0,.5)` : undefined,
    backgroundColor: box ? hexAlpha(style.box_color ?? "000000", style.box_opacity ?? 100) : undefined,
    padding: box ? "0.1em 0.25em" : undefined,
    borderRadius: box ? "0.1em" : undefined,
    boxDecorationBreak: "clone",
    WebkitBoxDecorationBreak: "clone",
  };
  const position = style.position ?? "bottom";
  const edge = `${(position === "top" ? 0.12 : frame.margin) * 100}cqh`;
  const place: CSSProperties =
    style.y != null
      ? { top: `${style.y}%`, transform: "translateY(-50%)" }
      : position === "middle"
        ? { top: "50%", transform: "translateY(-50%)" }
        : position === "top"
          ? { top: edge }
          : { bottom: edge };
  const animation = style.animation ?? "highlight";
  const corner = branding?.enabled ? branding.position : null;

  function wordStyle(i: number): CSSProperties | undefined {
    const hl = { color: `#${style.highlight_color}` };
    if (active < 0 || animation === "none") return undefined;
    if (animation === "karaoke") return i <= active ? hl : undefined;
    if (animation === "appear") return i > active ? { opacity: 0 } : i === active ? hl : undefined;
    if (i !== active) return undefined;
    return animation === "pop" ? { ...hl, display: "inline-block", transform: "scale(1.12)" } : hl;
  }

  return (
    <div
      className={cn(
        captionFontVariables,
        "relative w-full overflow-hidden rounded-xl bg-linear-to-br from-slate-600 via-slate-700 to-slate-900 select-none @container-size",
        className,
      )}
      style={{ aspectRatio: frame.aspect }}
      aria-hidden="true"
    >
      {background}
      {style.enabled !== false && shown.length > 0 && (
        <div className="absolute inset-x-[8%] flex justify-center text-center" style={place}>
          <span style={text}>
            {shown.map((w, i) => (
              <span key={i}>
                <span style={wordStyle(i)} className="transition-transform duration-100">
                  {w}
                </span>
                {i < shown.length - 1 ? " " : ""}
              </span>
            ))}
          </span>
        </div>
      )}
      {corner && (branding?.handle || logoUrl) && (
        <div
          className={cn(
            "absolute flex flex-col gap-[1cqh]",
            corner.startsWith("top") ? "top-[3.5cqh]" : "bottom-[3.5cqh]",
            corner.endsWith("left") ? "left-[3.5cqw] items-start" : "right-[3.5cqw] items-end",
            corner.startsWith("bottom") && "flex-col-reverse",
          )}
        >
          {logoUrl && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={logoUrl} alt="" className="w-[min(16cqw,16cqh)] opacity-90" />
          )}
          {branding?.handle && (
            <span
              className="font-bold text-white/80"
              style={{ fontFamily: captionFontFamily(style.font ?? "Archivo Black"), fontSize: "2.4cqh" }}
            >
              {branding.handle}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
