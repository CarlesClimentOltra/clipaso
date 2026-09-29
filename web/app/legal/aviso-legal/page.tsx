import type { Metadata } from "next";
import Link from "next/link";

import { legal } from "@/lib/legal";

export const metadata: Metadata = { title: "Aviso legal · Clipaso" };

export default function LegalNoticePage() {
  const { owner } = legal;
  return (
    <article>
      <h1>Aviso legal</h1>
      <p className="updated">Última actualización: {legal.updatedAt}</p>

      <p>
        En cumplimiento del artículo 10 de la Ley 34/2002, de servicios de la sociedad de la información y de comercio
        electrónico (LSSI), se informa de los datos del titular de este sitio web:
      </p>
      <ul>
        <li>Titular: {owner.name}</li>
        <li>NIF: {owner.taxId}</li>
        <li>Domicilio: {owner.address}</li>
        <li>
          Email: <a href={`mailto:${owner.email}`}>{owner.email}</a>
        </li>
        <li>Sitio web: {legal.site}</li>
        <li>Actividad: servicio en línea de edición automática de vídeo (Clipaso)</li>
      </ul>

      <h2>Condiciones de uso</h2>
      <p>
        El uso del servicio se rige por los <Link href="/legal/terminos">Términos del servicio</Link>. El tratamiento de
        datos personales se explica en la <Link href="/legal/privacidad">Política de privacidad</Link> y el uso de
        almacenamiento en el navegador en la <Link href="/legal/cookies">Política de cookies</Link>.
      </p>

      <h2>Propiedad intelectual</h2>
      <p>
        El diseño, el código y los textos de esta web pertenecen a su titular o se usan con licencia. El contenido que
        suben los usuarios y los clips generados son de sus autores, como se indica en los Términos del servicio.
      </p>
    </article>
  );
}
