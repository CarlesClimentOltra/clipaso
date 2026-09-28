// Idioma de la interfaz en el navegador: preferencia guardada o, si no hay, el del navegador.
// Es un "store externo" para poder leerlo también fuera de React (cliente de la API, errores de login).

export const LOCALES = ["es", "en"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "es";

const KEY = "smartcuts.locale";
const listeners = new Set<() => void>();
let memory: Locale | null = null;

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (LOCALES as readonly string[]).includes(value);
}

/** Español para quien navega en español o en otras lenguas de España; inglés para el resto. */
export function detectLocale(languages: readonly string[]): Locale {
  for (const lang of languages) {
    const code = lang.toLowerCase().slice(0, 2);
    if (["es", "ca", "gl", "eu"].includes(code)) return "es";
    if (code === "en") return "en";
  }
  return languages.length ? "en" : DEFAULT_LOCALE;
}

export function getStoredLocale(): Locale | null {
  try {
    const value = localStorage.getItem(KEY);
    return isLocale(value) ? value : memory;
  } catch {
    return memory;
  }
}

export function getLocale(): Locale {
  if (typeof window === "undefined") return DEFAULT_LOCALE;
  return getStoredLocale() ?? detectLocale(navigator.languages?.length ? navigator.languages : [navigator.language]);
}

export function storeLocale(locale: Locale) {
  memory = locale;
  try {
    localStorage.setItem(KEY, locale);
  } catch {
    // se queda en memoria durante la sesión
  }
  listeners.forEach((l) => l());
}

export function subscribeLocale(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}
