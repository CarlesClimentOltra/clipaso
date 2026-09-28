"use client";

import Link from "next/link";
import { CheckIcon, SaveIcon, Settings2Icon, SlidersHorizontalIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { CaptionPreview, type ClipFormat } from "@/components/caption-preview";
import { StyleEditor } from "@/components/style-editor";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, type CaptionStyle, type UserStyle } from "@/lib/api/client";
import { useStyleActions, useStyles } from "@/lib/api/hooks";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const KEYS = [
  "enabled", "font", "text_color", "highlight_color", "scale", "position", "y", "uppercase", "outline",
  "outline_color", "shadow", "box", "box_color", "box_opacity", "animation", "max_words",
] as const;

export function sameStyle(a: CaptionStyle, b: CaptionStyle) {
  return KEYS.every((k) => (a[k] ?? null) === (b[k] ?? null));
}

/** Nombre visible de un estilo (los de serie sin renombrar, traducidos). */
export function useStyleName() {
  const { t } = useI18n();
  return (s: UserStyle) => (s.builtin && !s.modified ? (t.styles.presets[s.id] ?? s.name) : s.name);
}

/** Tarjeta con la vista previa de un estilo; se anima al pasar el ratón o al estar elegida. */
export function StyleCard({
  style,
  name,
  selected,
  badge,
  disabled,
  onClick,
  format = "vertical",
}: {
  style: CaptionStyle;
  name: string;
  selected?: boolean;
  badge?: React.ReactNode;
  disabled?: boolean;
  onClick?: () => void;
  format?: ClipFormat;
}) {
  const [hover, setHover] = useState(false);
  return (
    <button
      type="button"
      role="radio"
      aria-checked={!!selected}
      disabled={disabled}
      onClick={onClick}
      onPointerEnter={() => setHover(true)}
      onPointerLeave={() => setHover(false)}
      onFocus={() => setHover(true)}
      onBlur={() => setHover(false)}
      className={cn(
        "group flex min-w-0 flex-col gap-1.5 rounded-2xl p-1.5 text-left outline-none transition-colors focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-60",
        selected ? "bg-primary/10 ring-2 ring-primary" : "hover:bg-muted",
      )}
    >
      <CaptionPreview style={style} format={format === "horizontal" ? "square" : format} animate={hover || !!selected}
                      className="rounded-xl" />
      <span className="flex min-w-0 items-center gap-1 px-0.5 text-xs font-medium">
        {selected && <CheckIcon className="size-3 shrink-0 text-brand-ink" />}
        <span className="truncate">{name}</span>
        {badge}
      </span>
    </button>
  );
}

/** Elige uno de tus estilos para este proyecto o clip y, si quieres, ajústalo solo aquí. */
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
  const { data } = useStyles();
  const actions = useStyleActions();
  const styleName = useStyleName();
  const [custom, setCustom] = useState(false);
  const [saving, setSaving] = useState<string | null>(null);
  const { t } = useI18n();
  const s = t.styles;
  const styles = data?.styles ?? [];
  const matched = styles.find((u) => sameStyle(value, u.style));
  const customCount = styles.filter((u) => !u.builtin).length;
  const canSave = !matched && !!data && customCount < data.max_custom;

  async function saveAsNew() {
    if (!saving?.trim()) return;
    try {
      await actions.create.mutateAsync({ name: saving.trim(), style: value });
      toast.success(s.savedNew);
      setSaving(null);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : s.saveError);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-5" role="radiogroup" aria-label={s.label}>
        {styles.map((u) => (
          <StyleCard
            key={u.id}
            style={u.style}
            name={styleName(u)}
            format={format}
            selected={matched?.id === u.id}
            disabled={disabled}
            onClick={() => onChange(u.style)}
          />
        ))}
        {!matched && data && (
          <StyleCard style={value} name={s.customLabel} format={format} selected disabled={disabled}
                     onClick={() => setCustom(true)} />
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" variant={custom ? "secondary" : "outline"} size="sm" onClick={() => setCustom(!custom)}
                aria-expanded={custom} disabled={disabled}>
          <SlidersHorizontalIcon /> {custom ? s.hide : s.customize}
        </Button>
        {canSave && saving === null && (
          <Button type="button" variant="ghost" size="sm" onClick={() => setSaving("")} disabled={disabled}>
            <SaveIcon /> {s.saveAsNew}
          </Button>
        )}
        <Link href="/account#estilos"
              className="ml-auto flex items-center gap-1 text-xs text-muted-foreground underline-offset-4 hover:underline">
          <Settings2Icon className="size-3.5" /> {s.manage}
        </Link>
      </div>

      {saving !== null && (
        <form
          className="flex flex-wrap items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            saveAsNew();
          }}
        >
          <Input autoFocus maxLength={40} placeholder={s.namePlaceholder} value={saving} className="h-8 max-w-60"
                 aria-label={s.name} onChange={(e) => setSaving(e.target.value)} />
          <Button type="submit" size="sm" disabled={!saving.trim() || actions.create.isPending}>{s.save}</Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => setSaving(null)}>{t.common.cancel}</Button>
        </form>
      )}

      {custom && (
        <div className="rounded-2xl border p-4">
          <p className="mb-4 text-xs text-muted-foreground">{s.onlyHere}</p>
          <StyleEditor value={value} onChange={onChange} disabled={disabled} />
        </div>
      )}
    </div>
  );
}
