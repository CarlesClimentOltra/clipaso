"use client";

import type { CSSProperties } from "react";

import type { BrandingPrefs, CaptionStyle } from "@/lib/api/client";
import { captionFontFamily, captionFontVariables } from "@/lib/caption-fonts";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export type ClipFormat = "vertical" | "square" | "horizontal";

// Mismas proporciones que los perfiles del motor (configs/output_profiles).
const FRAME: Record<ClipFormat, { aspect: string; size: number; margin: number }> = {
  vertical: { aspect: "9 / 16", size: 0.045, margin: 0.28 },
  square: { aspect: "1 / 1", size: 0.05, margin: 0.12 },
  horizontal: { aspect: "16 / 9", size: 0.045, margin: 0.12 },
};
const SIZE_FACTOR = { s: 0.8, m: 1, l: 1.25 } as const;

type Props = {
  style: CaptionStyle;
  format?: ClipFormat;
  words?: string[];
  activeIndex?: number;
  branding?: Pick<BrandingPrefs, "handle" | "position" | "enabled"> | null;
  logoUrl?: string | null;
  background?: React.ReactNode;
  className?: string;
};

/** Vista previa aproximada de cómo quedarán los subtítulos (y la marca) en el clip. */
export function CaptionPreview({
  style,
  format = "vertical",
  words,
  activeIndex = 1,
  branding,
  logoUrl,
  background,
  className,
}: Props) {
  const { t } = useI18n();
  words ??= t.styles.sample;
  const frame = FRAME[format];
  // Unidades relativas al alto del marco (container queries), como en el render real.
  const fontSize = `${frame.size * SIZE_FACTOR[style.size ?? "m"] * 100}cqh`;
  const outline = style.box ? undefined : "0.09em";
  const position = style.position ?? "bottom";
  const edge = `${(position === "top" ? 0.12 : frame.margin) * 100}cqh`;
  const text: CSSProperties = {
    fontFamily: captionFontFamily(style.font ?? "Archivo Black"),
    fontSize,
    color: `#${style.text_color}`,
    textTransform: style.uppercase ? "uppercase" : "none",
    lineHeight: 1.15,
    WebkitTextStroke: outline ? `${outline} #000` : undefined,
    paintOrder: "stroke fill",
    textShadow: style.box ? undefined : "0 0.06em 0.12em rgba(0,0,0,.45)",
    backgroundColor: style.box ? `#${style.box_color}` : undefined,
    padding: style.box ? "0.08em 0.3em" : undefined,
    borderRadius: style.box ? "0.12em" : undefined,
  };
  const corner = branding?.enabled ? branding.position : null;

  return (
    <div
      className={cn(
        captionFontVariables,
        "relative w-full overflow-hidden rounded-xl bg-linear-to-br from-slate-600 via-slate-700 to-slate-900 select-none [container-type:size]",
        className,
      )}
      style={{ aspectRatio: frame.aspect }}
      aria-hidden="true"
    >
      {background}
      {style.enabled !== false && format !== "horizontal" && (
        <div
          className="absolute inset-x-[8%] flex justify-center text-center"
          style={
            position === "middle"
              ? { top: "50%", transform: "translateY(-50%)" }
              : position === "top"
                ? { top: edge }
                : { bottom: edge }
          }
        >
          <span style={text}>
            {words.map((w, i) => (
              <span key={i} style={i === activeIndex ? { color: `#${style.highlight_color}` } : undefined}>
                {w}
                {i < words.length - 1 ? " " : ""}
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
            <img src={logoUrl} alt="" className="w-[16cqw] opacity-90" />
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
