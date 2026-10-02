// Paddle.js (pago con Paddle Billing). Se carga solo al pulsar «Mejorar»: ni la portada ni la app lo descargan.

type PaddleEvent = { name?: string };
type PaddleApi = {
  Environment: { set: (env: string) => void };
  Initialize: (opts: { token: string; eventCallback?: (e: PaddleEvent) => void }) => void;
  Checkout: { open: (opts: Record<string, unknown>) => void };
};

declare global {
  interface Window {
    Paddle?: PaddleApi;
  }
}

const SCRIPT_URL = "https://cdn.paddle.com/paddle/v2/paddle.js";
let ready: Promise<PaddleApi> | null = null;
let onEvent: ((name: string) => void) | null = null;

function load(environment: string, token: string): Promise<PaddleApi> {
  ready ??= new Promise((resolve, reject) => {
    const init = () => {
      const paddle = window.Paddle;
      if (!paddle) return reject(new Error("paddle"));
      if (environment === "sandbox") paddle.Environment.set("sandbox");
      paddle.Initialize({ token, eventCallback: (e) => onEvent?.(e.name ?? "") });
      resolve(paddle);
    };
    if (window.Paddle) return init();
    const script = document.createElement("script");
    script.src = SCRIPT_URL;
    script.async = true;
    script.onload = init;
    script.onerror = () => {
      ready = null;
      reject(new Error("paddle"));
    };
    document.head.appendChild(script);
  });
  return ready;
}

/** Abre el pago de Paddle encima de la página. `onEvent` recibe sus eventos (p. ej. «checkout.completed»). */
export async function openCheckout(opts: {
  environment: string;
  token: string;
  priceId: string;
  email?: string;
  userId: string;
  locale: string;
  onEvent: (name: string) => void;
}) {
  onEvent = opts.onEvent;
  const paddle = await load(opts.environment, opts.token);
  paddle.Checkout.open({
    items: [{ priceId: opts.priceId, quantity: 1 }],
    customer: opts.email ? { email: opts.email } : undefined,
    customData: { user_id: opts.userId }, // el webhook lo usa para saber a qué cuenta aplicar el plan
    settings: { displayMode: "overlay", theme: "light", locale: opts.locale, allowLogout: false },
  });
}
