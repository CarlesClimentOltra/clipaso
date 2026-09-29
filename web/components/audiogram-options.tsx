"use client";

import { CheckIcon, ImagePlusIcon, XIcon } from "lucide-react";
import { useRef } from "react";
import { toast } from "sonner";

import type { ClipFormat } from "@/components/caption-preview";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const BACKGROUNDS = ["0F172A", "4C1D95", "7F1D1D", "064E3B", "0C4A6E", "111111"];
const WAVES = ["B6E34A", "FFFFFF", "00E5FF", "FFE600", "FF3B81", "A78BFA"];
const WAVE = [4, 9, 14, 8, 18, 11, 6, 15, 20, 9, 5, 13, 17, 7, 10, 16, 6, 12, 8, 4];
const ASPECT: Record<ClipFormat, string> = { vertical: "aspect-9/16", square: "aspect-square", horizontal: "aspect-video" };
const MAX_SIDE = 1600;

export type AudiogramLook = { audiogram_title: string; audiogram_color: string; audiogram_accent: string };

/** Lee una imagen del usuario y la reduce a JPEG (como mucho 1600 px) para enviarla con el proyecto. */
function readImage(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, MAX_SIDE / Math.max(img.width, img.height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(img.width * scale);
      canvas.height = Math.round(img.height * scale);
      canvas.getContext("2d")!.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      resolve(canvas.toDataURL("image/jpeg", 0.88));
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("imagen"));
    };
    img.src = url;
  });
}

function Swatches({ label, colors, value, onChange, disabled }: {
  label: string; colors: string[]; value: string; onChange: (c: string) => void; disabled?: boolean;
}) {
  return (
    <div className="flex flex-col gap-2">
      <Label>{label}</Label>
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label={label}>
        {colors.map((c) => (
          <button key={c} type="button" role="radio" aria-checked={value === c} aria-label={`#${c}`} disabled={disabled}
                  onClick={() => onChange(c)} style={{ background: `#${c}` }}
                  className={cn("flex size-8 items-center justify-center rounded-full ring-1 ring-black/15 outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                                value === c && "ring-2 ring-primary ring-offset-2 ring-offset-background")}>
            {value === c && <CheckIcon className="size-4 text-white mix-blend-difference" />}
          </button>
        ))}
      </div>
    </div>
  );
}

/** Vista aproximada del audiograma: imagen (o degradado), título y onda. */
function Preview({ look, image, logoUrl, format }: {
  look: AudiogramLook; image: string | null; logoUrl?: string | null; format: ClipFormat;
}) {
  const art = image ?? logoUrl ?? null;
  return (
    <div className={cn("relative mx-auto flex w-full flex-col items-center overflow-hidden rounded-2xl shadow-sm",
                       ASPECT[format], format === "vertical" ? "max-w-[200px]" : "max-w-[320px]")}
         style={art ? undefined : { background: `linear-gradient(#${look.audiogram_color}, #000)` }}>
      {art && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={art} alt="" className="absolute inset-0 size-full scale-110 object-cover blur-md brightness-50" />
      )}
      <div className="relative flex size-full flex-col items-center justify-center gap-[6%] p-[6%]">
        {look.audiogram_title.trim() && (
          <p className="line-clamp-2 text-center text-[11px] leading-tight font-extrabold text-white [text-shadow:0_1px_2px_#000]">
            {look.audiogram_title}
          </p>
        )}
        {art && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={art} alt="" className="aspect-square w-[56%] rounded-md object-cover shadow-md" />
        )}
        <div className="flex h-8 w-[84%] items-center justify-between">
          {WAVE.map((v, i) => (
            <span key={i} className="w-[3%] rounded-full" style={{ height: `${v * 4}%`, background: `#${look.audiogram_accent}` }} />
          ))}
        </div>
      </div>
    </div>
  );
}

export function AudiogramOptions({
  look, onChange, image, onImage, logoUrl, format, disabled,
}: {
  look: AudiogramLook;
  onChange: (look: AudiogramLook) => void;
  image: string | null;
  onImage: (image: string | null) => void;
  logoUrl?: string | null;
  format: ClipFormat;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  const a = t.audiogram;
  const input = useRef<HTMLInputElement>(null);
  const set = (patch: Partial<AudiogramLook>) => onChange({ ...look, ...patch });

  async function pick(file: File | undefined) {
    if (!file) return;
    try {
      onImage(await readImage(file));
    } catch {
      toast.error(a.imageError);
    }
    if (input.current) input.current.value = "";
  }

  return (
    <div className="grid gap-5 rounded-2xl border bg-muted/30 p-4 sm:p-5 md:grid-cols-[1fr_200px]">
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-2">
          <Label htmlFor="audiogram-title">
            {a.title_} <span className="font-normal text-muted-foreground">{t.common.optional}</span>
          </Label>
          <Input id="audiogram-title" maxLength={90} value={look.audiogram_title} disabled={disabled}
                 placeholder={a.titlePlaceholder} onChange={(e) => set({ audiogram_title: e.target.value })} />
          <p className="text-xs text-muted-foreground">{a.titleHint}</p>
        </div>
        <div className="flex flex-col gap-2">
          <Label>{a.image}</Label>
          <div className="flex flex-wrap items-center gap-2">
            <input ref={input} type="file" accept="image/png,image/jpeg,image/webp" className="hidden"
                   onChange={(e) => pick(e.target.files?.[0])} />
            <Button type="button" variant="outline" size="sm" disabled={disabled} onClick={() => input.current?.click()}>
              <ImagePlusIcon /> {a.chooseImage}
            </Button>
            {image && (
              <Button type="button" variant="ghost" size="sm" disabled={disabled} onClick={() => onImage(null)}>
                <XIcon /> {a.removeImage}
              </Button>
            )}
          </div>
          <p className="text-xs text-muted-foreground">{a.imageHint}</p>
        </div>
        {!image && !logoUrl && (
          <Swatches label={a.background} colors={BACKGROUNDS} value={look.audiogram_color} disabled={disabled}
                    onChange={(audiogram_color) => set({ audiogram_color })} />
        )}
        <Swatches label={a.wave} colors={WAVES} value={look.audiogram_accent} disabled={disabled}
                  onChange={(audiogram_accent) => set({ audiogram_accent })} />
      </div>
      <div className="flex flex-col gap-2">
        <span className="text-xs text-muted-foreground">{a.preview}</span>
        <Preview look={look} image={image} logoUrl={logoUrl} format={format} />
      </div>
    </div>
  );
}
