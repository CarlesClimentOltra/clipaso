"use client";

import { CheckIcon, SlidersHorizontalIcon } from "lucide-react";
import { useState } from "react";

import { CaptionPreview, type ClipFormat } from "@/components/caption-preview";
import { Segmented } from "@/components/segmented";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type { CaptionPreset, CaptionStyle } from "@/lib/api/client";
import { useClipOptions } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";

function sameStyle(a: CaptionStyle, b: CaptionStyle) {
  const keys = ["font", "text_color", "highlight_color", "size", "position", "uppercase", "box", "box_color"] as const;
  return keys.every((k) => (a[k] ?? null) === (b[k] ?? null)) && (a.enabled ?? true) === (b.enabled ?? true);
}

function ColorField({ id, label, value, onChange }: { id: string; label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label htmlFor={id} className="flex items-center gap-2 text-sm">
      <input
        id={id}
        type="color"
        value={`#${value}`}
        onChange={(e) => onChange(e.target.value.slice(1).toUpperCase())}
        className="size-8 cursor-pointer rounded-md border border-input bg-transparent p-0.5"
      />
      {label}
    </label>
  );
}

/** Plantillas de subtítulos con vista previa y ajustes finos. */
export function StylePicker({
  value,
  onChange,
  format = "vertical",
  disabled,
}: {
  value: CaptionStyle;
  onChange: (style: CaptionStyle) => void;
  format?: ClipFormat;
  disabled?: boolean;
}) {
  const { data: options } = useClipOptions();
  const [custom, setCustom] = useState(false);
  const presets: CaptionPreset[] = options?.presets ?? [];
  const set = (patch: Partial<CaptionStyle>) => onChange({ ...value, ...patch });
  const enabled = value.enabled !== false;

  if (format === "horizontal") {
    return (
      <p className="text-sm text-muted-foreground">
        En formato horizontal los clips no llevan subtítulos incrustados (puedes descargarlos en SRT).
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-6" role="radiogroup" aria-label="Estilo de subtítulos">
        {presets.map((p) => {
          const selected = sameStyle(value, p.style);
          return (
            <button
              key={p.id}
              type="button"
              role="radio"
              aria-checked={selected}
              disabled={disabled}
              onClick={() => onChange(p.style)}
              className={cn(
                "group flex flex-col gap-1.5 rounded-xl p-1 text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                selected ? "ring-2 ring-primary" : "hover:bg-muted",
              )}
            >
              <CaptionPreview style={p.style} format="vertical" words={["Hola", "mundo"]} activeIndex={1}
                              className="rounded-lg" />
              <span className="flex items-center gap-1 px-0.5 text-xs font-medium">
                {selected && <CheckIcon className="size-3 text-brand-ink" />}
                {p.name}
              </span>
            </button>
          );
        })}
      </div>

      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="self-start"
        onClick={() => setCustom(!custom)}
        aria-expanded={custom}
      >
        <SlidersHorizontalIcon /> {custom ? "Ocultar ajustes" : "Personalizar"}
      </Button>

      {custom && (
        <div className="grid gap-4 rounded-xl border p-4 sm:grid-cols-2">
          <div className="flex items-center justify-between gap-3 sm:col-span-2">
            <Label htmlFor="subs-enabled">Subtítulos incrustados</Label>
            <Switch id="subs-enabled" checked={enabled} onCheckedChange={(c: boolean) => set({ enabled: c })} />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="subs-font">Fuente</Label>
            <select
              id="subs-font"
              value={value.font ?? "Archivo Black"}
              disabled={!enabled}
              onChange={(e) => set({ font: e.target.value as CaptionStyle["font"] })}
              className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
            >
              {(options?.fonts ?? []).map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-2">
            <Label>Tamaño</Label>
            <Segmented
              label="Tamaño"
              value={value.size ?? "m"}
              disabled={!enabled}
              onChange={(size) => set({ size })}
              options={[
                { value: "s", label: "Pequeño" },
                { value: "m", label: "Medio" },
                { value: "l", label: "Grande" },
              ]}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label>Posición</Label>
            <Segmented
              label="Posición"
              value={value.position ?? "bottom"}
              disabled={!enabled}
              onChange={(position) => set({ position })}
              options={[
                { value: "top", label: "Arriba" },
                { value: "middle", label: "Centro" },
                { value: "bottom", label: "Abajo" },
              ]}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label>Colores</Label>
            <div className="flex flex-wrap gap-4">
              <ColorField id="c-text" label="Texto" value={value.text_color ?? "FFFFFF"} onChange={(v) => set({ text_color: v })} />
              <ColorField id="c-hl" label="Palabra activa" value={value.highlight_color ?? "00E5FF"}
                          onChange={(v) => set({ highlight_color: v })} />
              {value.box && (
                <ColorField id="c-box" label="Caja" value={value.box_color ?? "000000"} onChange={(v) => set({ box_color: v })} />
              )}
            </div>
          </div>
          <div className="flex items-center justify-between gap-3">
            <Label htmlFor="subs-upper">Mayúsculas</Label>
            <Switch id="subs-upper" checked={!!value.uppercase} disabled={!enabled}
                    onCheckedChange={(c: boolean) => set({ uppercase: c })} />
          </div>
          <div className="flex items-center justify-between gap-3">
            <Label htmlFor="subs-box">Texto sobre caja</Label>
            <Switch id="subs-box" checked={!!value.box} disabled={!enabled} onCheckedChange={(c: boolean) => set({ box: c })} />
          </div>
        </div>
      )}
    </div>
  );
}
