// Fuentes de los subtítulos para la vista previa. Son las mismas que usa el motor al renderizar
// (assets/fonts en el backend). next/font las sirve desde nuestro dominio: el navegador no contacta
// con Google. Sin precarga: solo se descargan en las pantallas que muestran una vista previa.

import { Anton, Archivo_Black, Bebas_Neue, Luckiest_Guy, Poppins } from "next/font/google";

const archivo = Archivo_Black({ weight: "400", subsets: ["latin"], variable: "--caption-archivo", preload: false });
const anton = Anton({ weight: "400", subsets: ["latin"], variable: "--caption-anton", preload: false });
const bebas = Bebas_Neue({ weight: "400", subsets: ["latin"], variable: "--caption-bebas", preload: false });
const poppins = Poppins({ weight: "800", subsets: ["latin"], variable: "--caption-poppins", preload: false });
const luckiest = Luckiest_Guy({ weight: "400", subsets: ["latin"], variable: "--caption-luckiest", preload: false });

/** Clases que declaran las variables CSS de todas las fuentes (se aplican en el contenedor de la vista previa). */
export const captionFontVariables = [archivo, anton, bebas, poppins, luckiest].map((f) => f.variable).join(" ");

const FAMILY: Record<string, string> = {
  "Archivo Black": "var(--caption-archivo)",
  Anton: "var(--caption-anton)",
  "Bebas Neue": "var(--caption-bebas)",
  Poppins: "var(--caption-poppins)",
  "Luckiest Guy": "var(--caption-luckiest)",
};

export function captionFontFamily(font: string): string {
  return `${FAMILY[font] ?? FAMILY["Archivo Black"]}, sans-serif`;
}
