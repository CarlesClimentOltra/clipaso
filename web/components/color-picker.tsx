"use client";

import { PipetteIcon } from "lucide-react";
import { useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

// Colores habituales en subtítulos de vídeos cortos.
const SWATCHES = [
  "FFFFFF", "000000", "FFE600", "FFD60A", "FF9500", "FF3B30", "FF2BD6", "B6E34A",
  "7CFC00", "00E5FF", "2F80FF", "8B5CF6",
];

type Hsv = { h: number; s: number; v: number };

function hexToHsv(hex: string): Hsv {
  const n = parseInt(hex, 16);
  const r = ((n >> 16) & 255) / 255, g = ((n >> 8) & 255) / 255, b = (n & 255) / 255;
  const max = Math.max(r, g, b), d = max - Math.min(r, g, b);
  let h = 0;
  if (d) {
    if (max === r) h = ((g - b) / d) % 6;
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h = (h * 60 + 360) % 360;
  }
  return { h, s: max ? d / max : 0, v: max };
}

function hsvToHex({ h, s, v }: Hsv): string {
  const f = (n: number) => {
    const k = (n + h / 60) % 6;
    return Math.round((v - v * s * Math.max(0, Math.min(k, 4 - k, 1))) * 255);
  };
  return [f(5), f(3), f(1)].map((x) => x.toString(16).padStart(2, "0")).join("").toUpperCase();
}

/** Arrastre dentro de un elemento: devuelve la posición relativa (0..1) en cada movimiento. */
function useDrag(onMove: (x: number, y: number) => void) {
  const ref = useRef<HTMLDivElement>(null);
  function handle(e: ReactPointerEvent) {
    const r = ref.current!.getBoundingClientRect();
    onMove(Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)));
  }
  return {
    ref,
    onPointerDown: (e: ReactPointerEvent) => {
      e.currentTarget.setPointerCapture(e.pointerId);
      handle(e);
    },
    onPointerMove: (e: ReactPointerEvent) => {
      if (e.currentTarget.hasPointerCapture(e.pointerId)) handle(e);
    },
  };
}

type EyeDropperCtor = new () => { open: () => Promise<{ sRGBHex: string }> };

/** Selector de color: muestras rápidas, degradado, tono, código HEX y cuentagotas (si el navegador lo tiene). */
export function ColorPicker({
  value,
  onChange,
  label,
  disabled,
}: {
  value: string;
  onChange: (hex: string) => void;
  label: string;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  const [hsv, setHsv] = useState(() => hexToHsv(value));
  const [draft, setDraft] = useState(value);
  const [seen, setSeen] = useState(value);
  // Si el valor cambia desde fuera (otro estilo), el selector lo sigue sin perder el tono de los grises.
  if (seen !== value) {
    setSeen(value);
    if (hsvToHex(hsv) !== value.toUpperCase()) setHsv(hexToHsv(value));
    setDraft(value.toUpperCase());
  }
  // El contenido del popover solo se pinta en el navegador, al abrirlo: aquí ya existe `window`.
  const dropper = typeof window === "undefined"
    ? undefined
    : (window as unknown as { EyeDropper?: EyeDropperCtor }).EyeDropper;

  function update(next: Hsv) {
    setHsv(next);
    onChange(hsvToHex(next));
  }

  const area = useDrag((x, y) => update({ ...hsv, s: x, v: 1 - y }));
  const hue = useDrag((x) => update({ ...hsv, h: Math.min(359.9, x * 360) }));

  return (
    <Popover>
      <PopoverTrigger
        disabled={disabled}
        className="flex items-center gap-2 rounded-lg border border-input py-1 pr-2.5 pl-1 text-sm outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"
      >
        <span className="size-6 rounded-md ring-1 ring-foreground/15" style={{ background: `#${value}` }} />
        <span>{label}</span>
      </PopoverTrigger>
      <PopoverContent className="flex w-60 flex-col gap-3">
        <div className="grid grid-cols-6 gap-1.5">
          {SWATCHES.map((c) => (
            <button
              key={c}
              type="button"
              aria-label={`#${c}`}
              onClick={() => {
                setHsv(hexToHsv(c));
                onChange(c);
              }}
              className={cn(
                "aspect-square rounded-md ring-1 ring-foreground/15 outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                value.toUpperCase() === c && "ring-2 ring-primary ring-offset-2 ring-offset-popover",
              )}
              style={{ background: `#${c}` }}
            />
          ))}
        </div>
        <div
          {...area}
          role="presentation"
          className="relative h-32 cursor-crosshair touch-none rounded-lg"
          style={{
            background: `linear-gradient(to top, #000, transparent), linear-gradient(to right, #fff, hsl(${hsv.h} 100% 50%))`,
          }}
        >
          <span
            className="pointer-events-none absolute size-3.5 -translate-1/2 rounded-full border-2 border-white shadow ring-1 ring-black/30"
            style={{ left: `${hsv.s * 100}%`, top: `${(1 - hsv.v) * 100}%`, background: `#${value}` }}
          />
        </div>
        <div
          {...hue}
          role="presentation"
          className="relative h-3 cursor-pointer touch-none rounded-full"
          style={{ background: "linear-gradient(to right, #f00, #ff0, #0f0, #0ff, #00f, #f0f, #f00)" }}
        >
          <span
            className="pointer-events-none absolute top-1/2 size-4 -translate-1/2 rounded-full border-2 border-white shadow ring-1 ring-black/30"
            style={{ left: `${(hsv.h / 360) * 100}%`, background: `hsl(${hsv.h} 100% 50%)` }}
          />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">#</span>
          <Input
            aria-label={t.styles.hex}
            value={draft}
            maxLength={6}
            className="h-8 font-mono uppercase"
            onChange={(e) => {
              const v = e.target.value.replace(/[^0-9a-f]/gi, "").toUpperCase();
              setDraft(v);
              if (v.length === 6) {
                setHsv(hexToHsv(v));
                onChange(v);
              }
            }}
          />
          {dropper && (
            <button
              type="button"
              aria-label={t.styles.eyedropper}
              title={t.styles.eyedropper}
              className="grid size-8 shrink-0 place-items-center rounded-lg border border-input outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50"
              onClick={async () => {
                try {
                  const { sRGBHex } = await new dropper().open();
                  const hex = sRGBHex.replace("#", "").slice(0, 6).toUpperCase();
                  setHsv(hexToHsv(hex));
                  onChange(hex);
                } catch {
                  // cancelado por el usuario
                }
              }}
            >
              <PipetteIcon className="size-4" />
            </button>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
