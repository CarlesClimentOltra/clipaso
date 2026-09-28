"use client";

// Traducciones de la interfaz. `useI18n()` devuelve el diccionario del idioma activo (`t`), el idioma y
// utilidades de formato. En la portada el idioma lo fija la URL (/ o /en); en el resto, la preferencia
// guardada o el idioma del navegador.

import { createContext, useCallback, useContext, useMemo, useSyncExternalStore, type ReactNode } from "react";

import { en } from "@/lib/i18n/en";
import { es } from "@/lib/i18n/es";
import {
  DEFAULT_LOCALE,
  getLocale,
  storeLocale,
  subscribeLocale,
  type Locale,
} from "@/lib/i18n/store";

export type Dict = typeof es;
export type { Locale };
export { LOCALES } from "@/lib/i18n/store";

export const DICTIONARIES: Record<Locale, Dict> = { es, en };
const INTL: Record<Locale, string> = { es: "es-ES", en: "en-GB" };

/** Diccionario fuera de React (cliente de la API, errores de login). */
export function dictionary(locale: Locale = getLocale()): Dict {
  return DICTIONARIES[locale];
}

type I18nValue = {
  locale: Locale;
  t: Dict;
  setLocale: (locale: Locale) => void;
  formatDate: (date: Date | string, options: Intl.DateTimeFormatOptions) => string;
  intl: string;
};

const I18nContext = createContext<I18nValue | null>(null);

/** Con `locale` fijo (páginas públicas por idioma) no se lee la preferencia del navegador. */
export function I18nProvider({ locale: fixed, children }: { locale?: Locale; children: ReactNode }) {
  // En el servidor y durante la hidratación se usa el idioma por defecto; después, el del usuario.
  const detected = useSyncExternalStore(subscribeLocale, getLocale, () => DEFAULT_LOCALE);
  const locale = fixed ?? detected;
  const setLocale = useCallback((next: Locale) => storeLocale(next), []);
  const value = useMemo<I18nValue>(() => {
    const intl = INTL[locale];
    return {
      locale,
      t: DICTIONARIES[locale],
      setLocale,
      intl,
      formatDate: (date, options) => new Intl.DateTimeFormat(intl, options).format(new Date(date)),
    };
  }, [locale, setLocale]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n debe usarse dentro de <I18nProvider>");
  return ctx;
}
