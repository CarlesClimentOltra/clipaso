"use client";

import Link from "next/link";
import { MonitorIcon, SmartphoneIcon, SquareIcon } from "lucide-react";

import { CaptionPreview, type ClipFormat } from "@/components/caption-preview";
import { Segmented } from "@/components/segmented";
import { StylePicker } from "@/components/style-picker";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type { CaptionStyle, JobOptions, Me } from "@/lib/api/client";
import { useClipOptions, usePreferences } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";

const FORMAT_ICON = { vertical: SmartphoneIcon, square: SquareIcon, horizontal: MonitorIcon } as const;

export type ProjectOptionsValue = Required<Omit<JobOptions, "caption_style">> & { caption_style: CaptionStyle };

export function ProjectOptions({
  me,
  value,
  onChange,
  disabled,
}: {
  me: Me;
  value: ProjectOptionsValue;
  onChange: (value: ProjectOptionsValue) => void;
  disabled?: boolean;
}) {
  const { data: options } = useClipOptions();
  const { data: prefs } = usePreferences();
  const set = (patch: Partial<ProjectOptionsValue>) => onChange({ ...value, ...patch });
  const format = value.format as ClipFormat;
  const hasBrand = !!prefs && (!!prefs.branding.handle || prefs.branding.has_logo);
  const duration = options?.durations.find((d) => d.id === value.duration);

  return (
    <div className="flex flex-col gap-6">
      <fieldset className="flex flex-col gap-2" disabled={disabled}>
        <legend className="mb-2 text-sm font-medium">Formato</legend>
        <div className="grid gap-2 sm:grid-cols-3" role="radiogroup" aria-label="Formato">
          {(options?.formats ?? []).map((f) => {
            const Icon = FORMAT_ICON[f.id as ClipFormat] ?? SmartphoneIcon;
            const selected = value.format === f.id;
            return (
              <button
                key={f.id}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => set({ format: f.id as ProjectOptionsValue["format"] })}
                className={cn(
                  "flex items-center gap-3 rounded-xl border p-3 text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                  selected ? "border-primary bg-primary/5 ring-1 ring-primary" : "hover:bg-muted/50",
                )}
              >
                <Icon className={cn("size-5 shrink-0", selected ? "text-brand-ink" : "text-muted-foreground")} />
                <span>
                  <span className="block text-sm font-medium">{f.label}</span>
                  <span className="block text-xs text-muted-foreground">{f.hint}</span>
                </span>
              </button>
            );
          })}
        </div>
      </fieldset>

      <div className="flex flex-col gap-2">
        <Label>Duración de los clips</Label>
        <div className="flex flex-wrap items-center gap-3">
          <Segmented
            label="Duración de los clips"
            value={value.duration}
            disabled={disabled}
            onChange={(duration) => set({ duration })}
            options={(options?.durations ?? []).map((d) => ({ value: d.id as ProjectOptionsValue["duration"], label: d.label }))}
          />
          {duration && <span className="text-xs text-muted-foreground">{duration.hint}</span>}
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor="topic">
          Tema <span className="font-normal text-muted-foreground">(opcional)</span>
        </Label>
        <Input
          id="topic"
          maxLength={200}
          placeholder="Por ejemplo: los momentos donde hablo de dinero"
          value={value.topic}
          disabled={disabled}
          onChange={(e) => set({ topic: e.target.value })}
        />
        <p className="text-xs text-muted-foreground">La IA dará prioridad a los fragmentos sobre ese tema.</p>
      </div>

      <div className="flex flex-col gap-3">
        <Label>Estilo de los subtítulos</Label>
        <div className="grid gap-4 md:grid-cols-[1fr_160px]">
          <StylePicker value={value.caption_style} onChange={(caption_style) => set({ caption_style })} format={format}
                       disabled={disabled} />
          {format !== "horizontal" && (
            <CaptionPreview
              style={value.caption_style}
              format={format}
              branding={value.branding && prefs ? prefs.branding : null}
              logoUrl={value.branding ? prefs?.logo_url : null}
              className="hidden self-start md:block"
            />
          )}
        </div>
      </div>

      <div className="flex items-start justify-between gap-4 rounded-xl border p-4">
        <div className="flex flex-col gap-1">
          <Label htmlFor="branding">Añadir mi marca</Label>
          <p className="text-xs text-muted-foreground">
            {hasBrand ? (
              <>
                {prefs!.branding.handle || "Tu logo"} en una esquina de cada clip.{" "}
                <Link href="/account" className="underline underline-offset-4">Cambiar</Link>
              </>
            ) : (
              <>
                Añade tu logo o tu @usuario desde{" "}
                <Link href="/account" className="underline underline-offset-4">Mi cuenta</Link>.
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
          <span className="font-medium">Guardar el vídeo original para editar los clips y pedir más</span>
          <span className="block text-xs text-muted-foreground">
            Se guarda mientras el proyecto esté disponible ({me.plan.retention_days} días) y después se borra. Si lo
            desmarcas, se borra en cuanto terminen tus clips.
          </span>
        </span>
      </label>
    </div>
  );
}
