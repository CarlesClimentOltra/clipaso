"use client";

import {
  AlignVerticalJustifyCenterIcon,
  PaletteIcon,
  SparklesIcon,
  SquareIcon,
  TypeIcon,
} from "lucide-react";

import { ColorPicker } from "@/components/color-picker";
import { Segmented } from "@/components/segmented";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import type { CaptionStyle } from "@/lib/api/client";
import { CAPTION_FONTS, captionFontFamily, captionFontVariables } from "@/lib/caption-fonts";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type Animation = CaptionStyle["animation"];
const ANIMATIONS: Animation[] = ["highlight", "pop", "karaoke", "appear", "none"];
// Altura (en %) que corresponde a cada posición rápida en vertical, para arrancar el ajuste fino.
const POSITION_Y = { top: 16, middle: 50, bottom: 70 } as const;

function Section({ icon: Icon, title, children }: { icon: typeof TypeIcon; title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h4 className="flex items-center gap-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        <Icon className="size-3.5" /> {title}
      </h4>
      {children}
    </section>
  );
}

function SliderRow({
  id,
  label,
  value,
  min,
  max,
  step = 1,
  format,
  disabled,
  onChange,
}: {
  id: string;
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  format?: (v: number) => string;
  disabled?: boolean;
  onChange: (v: number) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between text-sm">
        <Label id={id}>{label}</Label>
        <span className="text-xs text-muted-foreground tabular-nums">{format ? format(value) : value}</span>
      </div>
      <Slider
        aria-labelledby={id}
        value={[value]}
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        onValueChange={(v: number | readonly number[]) => onChange(Array.isArray(v) ? v[0] : (v as number))}
      />
    </div>
  );
}

/** Todos los ajustes de un estilo de subtítulos, agrupados por secciones. */
export function StyleEditor({
  value,
  onChange,
  disabled,
}: {
  value: CaptionStyle;
  onChange: (style: CaptionStyle) => void;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  const s = t.styles;
  const set = (patch: Partial<CaptionStyle>) => onChange({ ...value, ...patch });
  const enabled = value.enabled !== false;
  const off = disabled || !enabled;

  return (
    <div className="@container flex flex-col gap-6">
      <div className="flex items-center justify-between gap-3 rounded-xl bg-muted/60 px-4 py-3">
        <div>
          <Label htmlFor="subs-enabled">{s.burnIn}</Label>
          <p className="text-xs text-muted-foreground">{s.burnInHint}</p>
        </div>
        <Switch id="subs-enabled" checked={enabled} disabled={disabled}
                onCheckedChange={(c: boolean) => set({ enabled: c })} />
      </div>

      <Section icon={TypeIcon} title={s.sections.text}>
        <div className="grid gap-4 @md:grid-cols-2">
          <div className="flex flex-col gap-2">
            <Label>{s.font}</Label>
            <Select
              value={value.font}
              disabled={off}
              onValueChange={(v) => v && set({ font: v as CaptionStyle["font"] })}
            >
              <SelectTrigger className={cn(captionFontVariables, "w-full")} aria-label={s.font}>
                <SelectValue>
                  {(v: string) => <span style={{ fontFamily: captionFontFamily(v) }}>{v}</span>}
                </SelectValue>
              </SelectTrigger>
              <SelectContent className={captionFontVariables}>
                {CAPTION_FONTS.map((f) => (
                  <SelectItem key={f} value={f}>
                    <span className="text-base" style={{ fontFamily: captionFontFamily(f) }}>{f}</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-end justify-between gap-3 pb-1">
            <Label htmlFor="subs-upper">{s.uppercase}</Label>
            <Switch id="subs-upper" checked={!!value.uppercase} disabled={off}
                    onCheckedChange={(c: boolean) => set({ uppercase: c })} />
          </div>
          <SliderRow id="subs-scale" label={s.size} value={value.scale} min={50} max={200} step={5} disabled={off}
                     format={(v) => `${v} %`} onChange={(scale) => set({ scale })} />
          <SliderRow id="subs-words" label={s.maxWords} value={value.max_words} min={1} max={8} disabled={off}
                     format={(v) => s.wordsCount(v)} onChange={(max_words) => set({ max_words })} />
        </div>
      </Section>

      <Section icon={SparklesIcon} title={s.sections.animation}>
        <div className="grid grid-cols-2 gap-2 @md:grid-cols-3 @2xl:grid-cols-5" role="radiogroup" aria-label={s.sections.animation}>
          {ANIMATIONS.map((a) => {
            const selected = value.animation === a;
            return (
              <button
                key={a}
                type="button"
                role="radio"
                aria-checked={selected}
                disabled={off}
                onClick={() => set({ animation: a })}
                className={cn(
                  "flex flex-col gap-0.5 rounded-xl border p-2.5 text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50",
                  selected ? "border-primary bg-primary/10 ring-1 ring-primary" : "hover:bg-muted/60",
                )}
              >
                <span className="text-sm font-medium">{s.animations[a][0]}</span>
                <span className="text-xs leading-snug text-muted-foreground">{s.animations[a][1]}</span>
              </button>
            );
          })}
        </div>
      </Section>

      <Section icon={PaletteIcon} title={s.sections.colors}>
        <div className="flex flex-wrap gap-2">
          <ColorPicker label={s.text} value={value.text_color} disabled={off} onChange={(v) => set({ text_color: v })} />
          <ColorPicker label={s.highlight} value={value.highlight_color} disabled={off || value.animation === "none"}
                       onChange={(v) => set({ highlight_color: v })} />
          {!value.box && (
            <ColorPicker label={s.outline} value={value.outline_color} disabled={off || value.outline === 0}
                         onChange={(v) => set({ outline_color: v })} />
          )}
        </div>
        {!value.box && (
          <div className="grid gap-4 @md:grid-cols-2">
            <SliderRow id="subs-outline" label={s.outlineWidth} value={value.outline} min={0} max={12} disabled={off}
                       format={(v) => (v ? String(v) : s.none)} onChange={(outline) => set({ outline })} />
            <SliderRow id="subs-shadow" label={s.shadow} value={value.shadow} min={0} max={12} disabled={off}
                       format={(v) => (v ? String(v) : s.none)} onChange={(shadow) => set({ shadow })} />
          </div>
        )}
      </Section>

      <Section icon={SquareIcon} title={s.sections.background}>
        <div className="flex items-center justify-between gap-3">
          <div>
            <Label htmlFor="subs-box">{s.boxToggle}</Label>
            <p className="text-xs text-muted-foreground">{s.boxHint}</p>
          </div>
          <Switch id="subs-box" checked={!!value.box} disabled={off} onCheckedChange={(c: boolean) => set({ box: c })} />
        </div>
        {value.box && (
          <div className="grid items-end gap-4 @md:grid-cols-[auto_1fr]">
            <ColorPicker label={s.box} value={value.box_color} disabled={off} onChange={(v) => set({ box_color: v })} />
            <SliderRow id="subs-box-opacity" label={s.opacity} value={value.box_opacity} min={0} max={100} step={5}
                       disabled={off} format={(v) => `${v} %`} onChange={(box_opacity) => set({ box_opacity })} />
          </div>
        )}
      </Section>

      <Section icon={AlignVerticalJustifyCenterIcon} title={s.sections.position}>
        <div className="flex flex-wrap items-center gap-3">
          <Segmented
            label={s.position}
            value={value.y == null ? value.position : ("custom" as never)}
            disabled={off}
            onChange={(position) => set({ position, y: null })}
            options={[
              { value: "top", label: s.positions.top },
              { value: "middle", label: s.positions.middle },
              { value: "bottom", label: s.positions.bottom },
            ]}
          />
          {value.y != null && <span className="text-xs text-muted-foreground">{s.customPosition}</span>}
        </div>
        <SliderRow id="subs-y" label={s.fineTune} value={value.y ?? POSITION_Y[value.position]} min={5} max={95}
                   disabled={off} format={(v) => s.fromTop(v)} onChange={(y) => set({ y })} />
      </Section>
    </div>
  );
}
