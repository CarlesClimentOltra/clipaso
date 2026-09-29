"use client";

// Marcas locales del navegador (primeros pasos). Si no hay localStorage, viven en memoria y ya.

import { useCallback, useSyncExternalStore } from "react";

const PREFIX = "clipaso.flag.";
const listeners = new Set<() => void>();
const memory = new Map<string, boolean>();

function read(key: string): boolean {
  try {
    return localStorage.getItem(PREFIX + key) === "1" || memory.get(key) === true;
  } catch {
    return memory.get(key) === true;
  }
}

export function setFlag(key: string, value = true) {
  memory.set(key, value);
  try {
    if (value) localStorage.setItem(PREFIX + key, "1");
    else localStorage.removeItem(PREFIX + key);
  } catch {
    // en memoria
  }
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

/** `[valor, activar]`. En el servidor siempre es `true` para no pintar nada que luego desaparezca. */
export function useFlag(key: string): [boolean, () => void] {
  const value = useSyncExternalStore(subscribe, () => read(key), () => true);
  const set = useCallback(() => setFlag(key), [key]);
  return [value, set];
}
