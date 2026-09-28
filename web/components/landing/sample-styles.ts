// Estilos de subtítulos usados en las ilustraciones de la portada (mismos valores que los
// predefinidos del backend, para que la portada no dependa de la API).

import type { CaptionStyle } from "@/lib/api/client";

/** Estilo completo con los valores por defecto del backend (CaptionStyle en saas/presets.py). */
export function captionStyle(patch: Partial<CaptionStyle> = {}): CaptionStyle {
  return {
    enabled: true,
    font: "Archivo Black",
    text_color: "FFFFFF",
    highlight_color: "00E5FF",
    scale: 100,
    position: "bottom",
    y: null,
    uppercase: true,
    outline: 4,
    outline_color: "000000",
    shadow: 2,
    box: false,
    box_color: "000000",
    box_opacity: 100,
    animation: "highlight",
    max_words: 3,
    ...patch,
  };
}

const base = captionStyle({ highlight_color: "B6E34A", scale: 125, position: "middle" });

export const SAMPLE_STYLES: Record<string, CaptionStyle> = {
  clasico: base,
  caja: { ...base, font: "Poppins", uppercase: false, box: true, box_opacity: 85, highlight_color: "FFE600" },
  titular: { ...base, font: "Bebas Neue", highlight_color: "FF3B30" },
};
