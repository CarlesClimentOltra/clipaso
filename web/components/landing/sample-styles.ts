// Estilos de subtítulos usados en las ilustraciones de la portada (mismos valores que los
// predefinidos del backend, para que la portada no dependa de la API).

import type { CaptionStyle } from "@/lib/api/client";

const base: CaptionStyle = {
  enabled: true,
  font: "Archivo Black",
  text_color: "FFFFFF",
  highlight_color: "B6E34A",
  size: "l",
  position: "middle",
  uppercase: true,
  box: false,
  box_color: "000000",
};

export const SAMPLE_STYLES: Record<string, CaptionStyle> = {
  clasico: base,
  caja: { ...base, font: "Poppins", uppercase: false, box: true, highlight_color: "FFE600" },
  titular: { ...base, font: "Bebas Neue", highlight_color: "FF3B30" },
};
