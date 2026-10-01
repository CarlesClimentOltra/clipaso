import type { Metadata } from "next";

import { legal } from "@/lib/legal";

export const metadata: Metadata = { title: "Política de cookies · Clipaso" };

const ITEMS = [
  {
    name: "sb-…-auth-token",
    purpose: "Mantener tu sesión iniciada (Supabase)",
    duration: "Hasta que cierras sesión",
  },
  {
    name: "clipaso.upload.…",
    purpose: "Recordar qué partes de un vídeo ya se han subido para continuar si se corta la conexión",
    duration: "Se borra al terminar la subida",
  },
  {
    name: "theme",
    purpose: "Recordar si prefieres el tema claro u oscuro",
    duration: "Hasta que la borras",
  },
];

export default function CookiesPage() {
  return (
    <article>
      <h1>Política de cookies</h1>
      <p className="updated">Última actualización: {legal.updatedAt}</p>

      <p>
        <strong>Clipaso no usa cookies de publicidad, de analítica ni de seguimiento, ni de terceros.</strong> Por eso
        no te mostramos ningún aviso para aceptarlas.
      </p>
      <p>
        Para funcionar, la web guarda en tu navegador (en su almacenamiento local, un mecanismo similar a las cookies)
        solo estos datos técnicos, que son estrictamente necesarios para prestarte el servicio que pides y que, por ello,
        no requieren consentimiento (art. 22.2 de la Ley 34/2002, LSSI):
      </p>
      <div className="overflow-x-auto">
        <table>
          <thead>
            <tr>
              <th>Nombre</th>
              <th>Para qué sirve</th>
              <th>Duración</th>
            </tr>
          </thead>
          <tbody>
            {ITEMS.map((i) => (
              <tr key={i.name}>
                <td>
                  <code>{i.name}</code>
                </td>
                <td>{i.purpose}</td>
                <td>{i.duration}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p>
        En los formularios de acceso usamos Cloudflare Turnstile para comprobar que no eres un bot. Según Cloudflare,
        Turnstile no usa cookies de seguimiento ni datos para publicidad; solo analiza señales técnicas del navegador
        para esa comprobación.
      </p>
      <p>
        Para saber cuántas personas visitan la web usamos Vercel Web Analytics, que no usa cookies ni guarda datos que
        te identifiquen: cuenta visitas de forma agregada y anónima.
      </p>
      <p>
        Puedes borrar estos datos en cualquier momento desde la configuración de tu navegador (borrando los datos del
        sitio). Si lo haces, se cerrará tu sesión.
      </p>
      <p>
        Si en el futuro incorporamos cookies que no sean estrictamente necesarias, actualizaremos esta política y te
        pediremos tu consentimiento antes de usarlas.
      </p>
    </article>
  );
}
