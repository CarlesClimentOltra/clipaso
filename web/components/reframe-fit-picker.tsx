"use client";

import { CheckIcon, ScanFaceIcon } from "lucide-react";

import type { ClipFormat } from "@/components/caption-preview";
import type { JobOptions } from "@/lib/api/client";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type Fit = NonNullable<JobOptions["reframe_fit"]>;
const FITS: Fit[] = ["auto", "blur_pad", "center"];
const ASPECT: Record<ClipFormat, string> = { vertical: "aspect-9/16", square: "aspect-square", horizontal: "aspect-video" };

/** Un fotograma del vídeo del usuario encajado en el formato nuevo, como quedaría (aproximado). */
function FitPreview({ fit, format, src }: { fit: Fit; format: ClipFormat; src: string | null }) {
  const frame = src ? `${src}#t=1` : null;
  return (
    <div className={cn("relative mx-auto h-28 overflow-hidden rounded-lg bg-slate-900 ring-1 ring-black/10", ASPECT[format])}>
      {frame && fit === "blur_pad" && (
        <>
          <video src={frame} muted playsInline preload="metadata" aria-hidden
                 className="absolute inset-0 size-full scale-110 object-cover blur-md brightness-75" />
          <video src={frame} muted playsInline preload="metadata" aria-hidden
                 className="relative size-full object-contain" />
        </>
      )}
      {frame && fit !== "blur_pad" && (
        <video src={frame} muted playsInline preload="metadata" aria-hidden className="size-full object-cover" />
      )}
      {fit === "auto" && (
        <ScanFaceIcon className="absolute top-1.5 right-1.5 size-4 rounded bg-black/50 p-0.5 text-lime-300" />
      )}
    </div>
  );
}

export function ReframeFitPicker({
  value,
  onChange,
  format,
  src,
  disabled,
}: {
  value: Fit;
  onChange: (fit: Fit) => void;
  format: ClipFormat;
  src: string | null;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  const r = t.reframe;
  return (
    <fieldset className="flex flex-col gap-2" disabled={disabled}>
      <legend className="mb-2 text-sm font-medium">{r.fit}</legend>
      <div className="grid gap-2 sm:grid-cols-3" role="radiogroup" aria-label={r.fit}>
        {FITS.map((fit) => {
          const selected = value === fit;
          return (
            <button
              key={fit}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => onChange(fit)}
              className={cn(
                "flex flex-col gap-3 rounded-xl border p-3 text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                selected ? "border-primary bg-primary/5 ring-1 ring-primary" : "hover:bg-muted/50",
              )}
            >
              <FitPreview fit={fit} format={format} src={src} />
              <span>
                <span className="flex items-center gap-1 text-sm font-medium">
                  {selected && <CheckIcon className="size-3.5 text-brand-ink" />} {r.fits[fit][0]}
                </span>
                <span className="block text-xs text-muted-foreground">{r.fits[fit][1]}</span>
              </span>
            </button>
          );
        })}
      </div>
      {src && <p className="text-xs text-muted-foreground">{r.previewNote}</p>}
    </fieldset>
  );
}
