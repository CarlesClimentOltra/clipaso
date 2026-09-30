"use client";

import Link from "next/link";
import { FrameIcon, MonitorIcon, SmartphoneIcon, SquareIcon } from "lucide-react";

import { CaptionPreview, type ClipFormat } from "@/components/caption-preview";
import { Segmented } from "@/components/segmented";
import { StylePicker } from "@/components/style-picker";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type { CaptionStyle, JobOptions, Me } from "@/lib/api/client";
import { useClipOptions, usePreferences } from "@/lib/api/hooks";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const FORMAT_ICON = { vertical: SmartphoneIcon, square: SquareIcon, horizontal: MonitorIcon, original: FrameIcon } as const;

export type ProjectOptionsValue = Required<Omit<JobOptions, "caption_style">> & { caption_style: CaptionStyle };

export function ProjectOptions({
  me,
  value,
  onChange,
  disabled,
  background,
  sourceFrame = "horizontal",
  subtitlesExtra,
  sameFormat,
  fitPicker,
}: {
  me: Me;
  value: ProjectOptionsValue;
  onChange: (value: ProjectOptionsValue) => void;
  disabled?: boolean;
  /** Fondo de la vista previa (p. ej. un fotograma del vídeo elegido). */
  background?: React.ReactNode;
  /** Encuadre del vídeo elegido (para la vista previa del formato «original»). */
  sourceFrame?: ClipFormat;
  /** Ajustes que solo tienen sentido con subtítulos (p. ej. traducirlos); se muestran bajo los estilos. */
  subtitlesExtra?: React.ReactNode;
  /** Cambiar formato: el formato que ya tiene el vídeo (no se puede elegir). */
  sameFormat?: ClipFormat | null;
  /** Cambiar formato: cómo encajar la imagen (va justo debajo del formato). */
  fitPicker?: React.ReactNode;
}) {
  const { data: options } = useClipOptions();
  const { data: prefs } = usePreferences();
  const { t } = useI18n();
  const o = t.options;
  const set = (patch: Partial<ProjectOptionsValue>) => onChange({ ...value, ...patch });
  // Vídeo entero (subtitular, sin silencios o cambiar formato): sin duración ni tema.
  const reframeMode = value.mode === "reframe";
  const subtitleMode = ["subtitle", "clean", "trailer", "audiogram"].includes(value.mode ?? "") || reframeMode;
  const format: ClipFormat = value.format === "original" ? sourceFrame : (value.format as ClipFormat);
  // «Original» solo tiene sentido con el vídeo entero y sin cambiar de formato (los clips se reencuadran siempre).
  // Un audiograma no tiene formato propio (sale de un audio).
  const withOriginal = subtitleMode && !reframeMode && value.mode !== "audiogram";
  const formats = (options?.formats ?? [])
    .filter((f) => withOriginal || f.id !== "original")
    .sort((a, b) => (subtitleMode ? Number(b.id === "original") - Number(a.id === "original") : 0));
  const hasBrand = !!prefs && (!!prefs.branding.handle || prefs.branding.has_logo);
  const durationHint = o.durations[value.duration]?.[1];
  const subtitlesOn = value.caption_style.enabled !== false;

  return (
    <div className="flex flex-col gap-6">
      <fieldset className="flex flex-col gap-2" disabled={disabled}>
        <legend className="mb-2 text-sm font-medium">{reframeMode ? t.reframe.to : o.format}</legend>
        <div className={cn("grid gap-2", withOriginal ? "sm:grid-cols-2 lg:grid-cols-4" : "sm:grid-cols-3")}
             role="radiogroup" aria-label={o.format}>
          {formats.map((f) => {
            const Icon = FORMAT_ICON[f.id as ClipFormat] ?? SmartphoneIcon;
            const selected = value.format === f.id;
            // Al cambiar de formato, el del propio vídeo no es una opción.
            const same = reframeMode && f.id === sameFormat;
            return (
              <button
                key={f.id}
                type="button"
                role="radio"
                aria-checked={selected}
                disabled={same}
                onClick={() => set({ format: f.id as ProjectOptionsValue["format"] })}
                className={cn(
                  "flex items-center gap-3 rounded-xl border p-3 text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-45",
                  selected ? "border-primary bg-primary/5 ring-1 ring-primary" : "hover:bg-muted/50",
                )}
              >
                <Icon className={cn("size-5 shrink-0", selected ? "text-brand-ink" : "text-muted-foreground")} />
                <span>
                  <span className="block text-sm font-medium">{o.formats[f.id]?.[0] ?? f.label}</span>
                  <span className="block text-xs text-muted-foreground">
                    {same ? t.reframe.same : o.formats[f.id]?.[1] ?? f.hint}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      </fieldset>

      {fitPicker}

      {!subtitleMode && (
        <>
          <div className="flex flex-col gap-2">
            <Label>{o.duration}</Label>
            <div className="flex flex-wrap items-center gap-3">
              <Segmented
                label={o.duration}
                value={value.duration}
                disabled={disabled}
                onChange={(duration) => set({ duration })}
                options={(options?.durations ?? []).map((d) => ({
                  value: d.id as ProjectOptionsValue["duration"],
                  label: o.durations[d.id]?.[0] ?? d.label,
                }))}
              />
              {durationHint && <span className="text-xs text-muted-foreground">{durationHint}</span>}
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="topic">
              {o.topic} <span className="font-normal text-muted-foreground">{t.common.optional}</span>
            </Label>
            <Input
              id="topic"
              maxLength={200}
              placeholder={o.topicPlaceholder}
              value={value.topic}
              disabled={disabled}
              onChange={(e) => set({ topic: e.target.value })}
            />
            <p className="text-xs text-muted-foreground">{o.topicHint}</p>
          </div>
        </>
      )}

      <div className="flex flex-col gap-3">
        <Label>{o.style}</Label>
        <div className={cn("grid gap-5", subtitlesOn && "md:grid-cols-[1fr_200px]")}>
          {/* Solo en «Solo subtitular» son obligatorios; en el resto, desactivados hasta que el usuario los pida. */}
          <div className="flex min-w-0 flex-col gap-5">
            <StylePicker value={value.caption_style} onChange={(caption_style) => set({ caption_style })}
                         format={format} disabled={disabled} optional={value.mode !== "subtitle"} />
            {subtitlesOn && subtitlesExtra}
          </div>
          <div className={cn("hidden", subtitlesOn && "md:block")}>
            <div className="sticky top-20 flex flex-col gap-2">
              <span className="text-xs text-muted-foreground">{t.brand.preview}</span>
              <CaptionPreview
                style={value.caption_style}
                format={format}
                animate
                branding={value.branding && prefs ? prefs.branding : null}
                logoUrl={value.branding ? prefs?.logo_url : null}
                background={background}
                className="rounded-2xl shadow-sm"
              />
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-start justify-between gap-4 rounded-xl border p-4">
        <div className="flex flex-col gap-1">
          <Label htmlFor="branding">{o.branding}</Label>
          <p className="text-xs text-muted-foreground">
            {hasBrand ? (
              <>
                {o.brandingOn(prefs!.branding.handle || o.yourLogo)}{" "}
                <Link href="/customize" className="underline underline-offset-4">{o.change}</Link>
              </>
            ) : (
              <>
                {o.brandingOffStart}{" "}
                <Link href="/customize" className="underline underline-offset-4">{t.header.customize}</Link>.
              </>
            )}
          </p>
        </div>
        <Switch
          id="branding"
          checked={value.branding && hasBrand}
          disabled={disabled || !hasBrand}
          onCheckedChange={(c: boolean) => set({ branding: c })}
        />
      </div>

      <label className="flex items-start gap-3 text-sm">
        <Checkbox
          checked={value.keep_source}
          disabled={disabled}
          onCheckedChange={(c: boolean) => set({ keep_source: c })}
          className="mt-0.5"
        />
        <span>
          <span className="font-medium">{o.keepTitle}</span>
          <span className="block text-xs text-muted-foreground">{o.keepText(me.plan.retention_days)}</span>
        </span>
      </label>
    </div>
  );
}
