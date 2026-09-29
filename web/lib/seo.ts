// Datos para buscadores y redes sociales: URL pública, metadatos por idioma y datos estructurados.

import type { Metadata } from "next";

import { en } from "@/lib/i18n/en";
import { es } from "@/lib/i18n/es";
import type { Locale } from "@/lib/i18n/store";

// Los diccionarios se importan directamente: este módulo se usa en el servidor (metadatos).
const DICTIONARIES = { es, en };

export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://smartcuts-kohl.vercel.app").replace(/\/$/, "");
const PATHS: Record<Locale, string> = { es: "/", en: "/en" };
const OG_LOCALE: Record<Locale, string> = { es: "es_ES", en: "en_GB" };

/** Metadatos de la portada de cada idioma, con las alternativas (hreflang) enlazadas entre sí. */
export function landingMetadata(locale: Locale): Metadata {
  const t = DICTIONARIES[locale].meta;
  return {
    title: { absolute: t.title },
    description: t.description,
    alternates: {
      canonical: PATHS[locale],
      languages: { es: PATHS.es, en: PATHS.en, "x-default": PATHS.es },
    },
    openGraph: {
      type: "website",
      url: PATHS[locale],
      siteName: "Clipaso",
      title: t.title,
      description: t.description,
      locale: OG_LOCALE[locale],
      alternateLocale: Object.values(OG_LOCALE).filter((l) => l !== OG_LOCALE[locale]),
    },
    twitter: { card: "summary_large_image", title: t.title, description: t.description },
  };
}

/** Datos estructurados (schema.org) para que los buscadores entiendan qué es Clipaso. */
export function landingJsonLd(locale: Locale) {
  const t = DICTIONARIES[locale].meta;
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "Clipaso",
    url: `${SITE_URL}${PATHS[locale] === "/" ? "" : PATHS[locale]}`,
    description: t.description,
    applicationCategory: "MultimediaApplication",
    operatingSystem: "Web",
    inLanguage: locale,
    offers: { "@type": "Offer", price: "0", priceCurrency: "EUR" },
  };
}
