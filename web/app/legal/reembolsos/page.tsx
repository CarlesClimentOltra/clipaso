import type { Metadata } from "next";
import Link from "next/link";

import { legal } from "@/lib/legal";

export const metadata: Metadata = { title: "Política de reembolsos" };

export default function RefundsPage() {
  const { owner } = legal;
  return (
    <article>
      <h1>Política de reembolsos</h1>
      <p className="updated">Última actualización: {legal.updatedAt}</p>

      <p>
        Los pagos de Clipaso los gestiona nuestro revendedor online <strong>Paddle.com</strong>, que actúa como vendedor
        (Merchant of Record) de todos los pedidos. Los reembolsos se tramitan a través de Paddle y se devuelven al mismo
        medio de pago que usaste.
      </p>

      <h2>1. Reembolso del primer pago (14 días)</h2>
      <p>
        Si no estás satisfecho con Clipaso, puedes pedir el <strong>reembolso completo de tu primer pago</strong> de una
        suscripción (mensual o anual) en los <strong>14 días</strong> siguientes a la compra, sin tener que dar
        explicaciones. Escríbenos a <a href={`mailto:${owner.email}`}>{owner.email}</a> desde el email de tu cuenta, o
        pídelo directamente a Paddle desde el enlace de tu recibo.
      </p>

      <h2>2. Renovaciones</h2>
      <p>
        Las renovaciones posteriores no se reembolsan, salvo cuando la ley lo exija o si el servicio no ha funcionado por
        causas atribuibles a nosotros. Puedes cancelar cuando quieras desde «Planes → Gestionar suscripción»: no se te
        volverá a cobrar y conservas el plan hasta el final del periodo pagado.
      </p>

      <h2>3. Cambios de plan</h2>
      <p>
        Si cambias a un plan inferior o de anual a mensual, la parte no usada del periodo en curso se te abona como saldo
        para los siguientes cobros. Si cambias a uno superior, se cobra solo la diferencia proporcional.
      </p>

      <h2>4. Fallos del servicio</h2>
      <p>
        Si un vídeo falla al procesarse por causas técnicas, los minutos se te devuelven automáticamente. Si un problema
        nuestro te impide usar el servicio, escríbenos y lo compensaremos o te reembolsaremos la parte afectada.
      </p>

      <h2>5. Cómo pedirlo</h2>
      <p>
        Escribe a <a href={`mailto:${owner.email}`}>{owner.email}</a> con el email de tu cuenta y, si lo tienes, el número
        de pedido del recibo de Paddle. Respondemos en un máximo de 3 días laborables. Consulta también los{" "}
        <Link href="/legal/terminos">términos del servicio</Link>.
      </p>

      <h2 lang="en">Refund policy (English summary)</h2>
      <p lang="en">
        Payments are processed by our online reseller Paddle.com, the Merchant of Record for all orders. You can request
        a full refund of your first subscription payment (monthly or yearly) within 14 days of purchase, no questions
        asked, by emailing <a href={`mailto:${owner.email}`}>{owner.email}</a> or through the link in your Paddle receipt.
        Renewals are not refundable except where required by law or when the service failed for reasons attributable to
        us. You can cancel anytime from «Plans → Manage subscription» and keep your plan until the end of the paid period.
      </p>
    </article>
  );
}
