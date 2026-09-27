"use client";

// Cloudflare Turnstile: comprueba que quien rellena el formulario no es un bot. Normalmente es
// invisible; solo pide un clic si detecta algo raro. Si no hay clave configurada no se muestra nada
// y el formulario funciona sin captcha (desarrollo local).

import { useEffect, useRef } from "react";

import { config } from "@/lib/config";

type TurnstileApi = {
  render: (el: HTMLElement, opts: Record<string, unknown>) => string;
  reset: (id: string) => void;
  remove: (id: string) => void;
};

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

const SCRIPT_URL = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
let scriptPromise: Promise<TurnstileApi> | null = null;

function loadTurnstile(): Promise<TurnstileApi> {
  scriptPromise ??= new Promise((resolve, reject) => {
    if (window.turnstile) return resolve(window.turnstile);
    const script = document.createElement("script");
    script.src = SCRIPT_URL;
    script.async = true;
    script.onload = () => (window.turnstile ? resolve(window.turnstile) : reject(new Error("turnstile")));
    script.onerror = () => {
      scriptPromise = null;
      reject(new Error("No se pudo cargar la verificación anti-bots"));
    };
    document.head.appendChild(script);
  });
  return scriptPromise;
}

export const captchaEnabled = () => config.turnstileSiteKey !== "";

/**
 * Widget de verificación. `onToken` recibe el token (o null si caduca o falla). Cada token sirve
 * una sola vez: cambia `resetKey` tras cada envío para pedir uno nuevo.
 */
export function Captcha({ onToken, resetKey = 0 }: { onToken: (token: string | null) => void; resetKey?: number }) {
  const container = useRef<HTMLDivElement>(null);
  const widgetId = useRef<string | null>(null);
  const onTokenRef = useRef(onToken);

  useEffect(() => {
    onTokenRef.current = onToken;
  }, [onToken]);

  useEffect(() => {
    if (!captchaEnabled()) return;
    let cancelled = false;
    loadTurnstile()
      .then((ts) => {
        if (cancelled || !container.current) return;
        widgetId.current = ts.render(container.current, {
          sitekey: config.turnstileSiteKey,
          language: "es",
          appearance: "interaction-only",
          callback: (token: string) => onTokenRef.current(token),
          "expired-callback": () => onTokenRef.current(null),
          "error-callback": () => onTokenRef.current(null),
        });
      })
      .catch(() => onTokenRef.current(null));
    return () => {
      cancelled = true;
      if (widgetId.current && window.turnstile) window.turnstile.remove(widgetId.current);
      widgetId.current = null;
    };
  }, []);

  useEffect(() => {
    if (resetKey && widgetId.current && window.turnstile) {
      onTokenRef.current(null);
      window.turnstile.reset(widgetId.current);
    }
  }, [resetKey]);

  if (!captchaEnabled()) return null;
  return <div ref={container} className="flex justify-center empty:hidden" />;
}
