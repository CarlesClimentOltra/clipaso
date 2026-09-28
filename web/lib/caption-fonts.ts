// Fuentes de los subtítulos para la vista previa. Son las mismas que usa el motor al renderizar
// (assets/fonts en el backend). next/font las sirve desde nuestro dominio: el navegador no contacta
// con Google. Sin precarga: solo se descargan en las pantallas que muestran una vista previa.

import {
  Anton,
  Archivo_Black,
  Bangers,
  Bebas_Neue,
  Inter,
  Luckiest_Guy,
  Montserrat,
  Oswald,
  Permanent_Marker,
  Poppins,
  Rubik,
} from "next/font/google";

const archivo = Archivo_Black({ weight: "400", subsets: ["latin"], variable: "--caption-archivo", preload: false });
const anton = Anton({ weight: "400", subsets: ["latin"], variable: "--caption-anton", preload: false });
const bebas = Bebas_Neue({ weight: "400", subsets: ["latin"], variable: "--caption-bebas", preload: false });
const poppins = Poppins({ weight: "800", subsets: ["latin"], variable: "--caption-poppins", preload: false });
const luckiest = Luckiest_Guy({ weight: "400", subsets: ["latin"], variable: "--caption-luckiest", preload: false });
const montserrat = Montserrat({ weight: "900", subsets: ["latin"], variable: "--caption-montserrat", preload: false });
const oswald = Oswald({ weight: "700", subsets: ["latin"], variable: "--caption-oswald", preload: false });
const bangers = Bangers({ weight: "400", subsets: ["latin"], variable: "--caption-bangers", preload: false });
const rubik = Rubik({ weight: "900", subsets: ["latin"], variable: "--caption-rubik", preload: false });
const marker = Permanent_Marker({ weight: "400", subsets: ["latin"], variable: "--caption-marker", preload: false });
const inter = Inter({ weight: "800", subsets: ["latin"], variable: "--caption-inter", preload: false });

/** Clases que declaran las variables CSS de todas las fuentes (se aplican en el contenedor de la vista previa). */
export const captionFontVariables = [
  archivo, anton, bebas, poppins, luckiest, montserrat, oswald, bangers, rubik, marker, inter,
].map((f) => f.variable).join(" ");

const FAMILY: Record<string, string> = {
  "Archivo Black": "var(--caption-archivo)",
  Anton: "var(--caption-anton)",
  "Bebas Neue": "var(--caption-bebas)",
  Poppins: "var(--caption-poppins)",
  "Luckiest Guy": "var(--caption-luckiest)",
  Montserrat: "var(--caption-montserrat)",
  Oswald: "var(--caption-oswald)",
  Bangers: "var(--caption-bangers)",
  Rubik: "var(--caption-rubik)",
  "Permanent Marker": "var(--caption-marker)",
  Inter: "var(--caption-inter)",
};

export const CAPTION_FONTS = Object.keys(FAMILY) as CaptionFont[];
export type CaptionFont =
  | "Archivo Black" | "Anton" | "Bebas Neue" | "Poppins" | "Luckiest Guy" | "Montserrat" | "Oswald" | "Bangers"
  | "Rubik" | "Permanent Marker" | "Inter";

export function captionFontFamily(font: string): string {
  return `${FAMILY[font] ?? FAMILY["Archivo Black"]}, sans-serif`;
}
