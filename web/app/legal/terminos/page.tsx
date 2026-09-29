import type { Metadata } from "next";
import Link from "next/link";

import { legal } from "@/lib/legal";

export const metadata: Metadata = { title: "Términos del servicio · Clipaso" };

export default function TermsPage() {
  const { owner } = legal;
  return (
    <article>
      <h1>Términos del servicio</h1>
      <p className="updated">Última actualización: {legal.updatedAt}</p>

      <p>
        Estos términos regulan el uso de Clipaso, un servicio que convierte vídeos largos en clips verticales con
        subtítulos mediante inteligencia artificial, prestado por {owner.name} (en adelante, «Clipaso»). Al crear una
        cuenta o usar el servicio los aceptas. Si no estás de acuerdo, no uses el servicio.
      </p>

      <h2>1. Cuenta</h2>
      <ul>
        <li>Debes tener al menos {legal.minAge} años y dar un email válido que controles.</li>
        <li>
          Eres responsable de mantener tu contraseña en secreto y de la actividad de tu cuenta. Avísanos si detectas un
          uso no autorizado.
        </li>
        <li>Una cuenta es personal: no la compartas ni la revendas.</li>
      </ul>

      <h2>2. Planes y minutos</h2>
      <ul>
        <li>
          Cada plan incluye unos minutos de vídeo al mes y unos límites (duración máxima por vídeo, número de clips,
          tamaño de archivo y días de conservación), que se muestran en la web antes de contratar.
        </li>
        <li>
          Al enviar un vídeo se reservan sus minutos. <strong>Si el procesamiento falla por causas técnicas, los minutos
          se devuelven automáticamente.</strong> Los minutos no usados no se acumulan al mes siguiente.
        </li>
        <li>
          Durante la fase de lanzamiento el servicio puede ofrecerse solo en su versión gratuita. Cuando haya planes de
          pago, sus precios, impuestos, forma de pago, renovación y cancelación se indicarán antes de la contratación y
          formarán parte de estos términos.
        </li>
      </ul>

      <h2>3. Tu contenido</h2>
      <ul>
        <li>
          <strong>Tus vídeos y los clips generados son tuyos.</strong> Clipaso no adquiere ningún derecho sobre ellos.
        </li>
        <li>
          Nos concedes únicamente el permiso necesario para almacenarlos y procesarlos con el fin de prestarte el
          servicio, durante el tiempo indicado en la <Link href="/legal/privacidad">Política de privacidad</Link>. No los
          usamos para entrenar modelos de IA, ni para publicidad, ni los mostramos a terceros.
        </li>
        <li>
          Garantizas que tienes todos los derechos necesarios sobre lo que subes (derechos de autor, música, imagen) y,
          cuando aparezcan otras personas, su autorización para grabarlas, procesar sus datos y publicar los clips.
        </li>
        <li>
          Para esos datos de terceros, tú eres el responsable del tratamiento y Clipaso actúa como encargado: los trata
          solo siguiendo tus instrucciones (generar tus clips), con las medidas de seguridad descritas en la política de
          privacidad, a través de los proveedores allí indicados, y los elimina en los plazos indicados en ella.
        </li>
      </ul>

      <h2>4. Usos prohibidos</h2>
      <p>No puedes usar Clipaso para subir o generar contenido que:</p>
      <ul>
        <li>Infrinja derechos de propiedad intelectual o de imagen de otras personas.</li>
        <li>Sea ilegal, incluido cualquier contenido de abuso sexual infantil, que denunciaremos a las autoridades.</li>
        <li>Incite al odio, la violencia o el acoso, o difunda información personal de terceros sin permiso.</li>
        <li>Suplante a otras personas o pretenda engañar sobre su origen de forma dañina.</li>
      </ul>
      <p>
        Tampoco puedes intentar acceder a cuentas o datos ajenos, sobrecargar el servicio, eludir los límites de tu plan
        (por ejemplo, con cuentas múltiples) ni hacer ingeniería inversa del servicio.
      </p>

      <h2>5. Resultados generados con IA</h2>
      <p>
        La selección de momentos, los títulos, el reencuadre y los subtítulos se generan de forma automática y pueden
        contener errores (por ejemplo, palabras mal transcritas o un encuadre imperfecto). Revisa cada clip antes de
        publicarlo: eres responsable de lo que publiques.
      </p>

      <h2>6. Disponibilidad y conservación</h2>
      <ul>
        <li>
          Trabajamos para que el servicio esté disponible y funcione bien, pero puede sufrir interrupciones por
          mantenimiento, fallos o causas ajenas a nosotros.
        </li>
        <li>
          Los clips se conservan durante los días que indica tu plan y después se borran automáticamente.{" "}
          <strong>Descarga los clips que quieras guardar</strong>: Clipaso no es un servicio de almacenamiento a largo
          plazo.
        </li>
        <li>Podemos mejorar o cambiar funciones del servicio; si un cambio te perjudica de forma relevante, te avisaremos.</li>
      </ul>

      <h2>7. Responsabilidad</h2>
      <p>
        Clipaso responde de los daños que cause por dolo o negligencia grave y en los demás casos que establezca la ley.
        No respondemos del uso que hagas de los clips ni del contenido que subas. Si eres consumidor, nada de lo previsto
        en estos términos limita los derechos que te reconoce la legislación de consumidores y usuarios.
      </p>

      <h2>8. Suspensión y baja</h2>
      <ul>
        <li>Puedes dejar de usar el servicio y eliminar tu cuenta cuando quieras desde «Mi cuenta».</li>
        <li>
          Podemos suspender o cerrar una cuenta que incumpla gravemente estos términos, en particular el apartado 4. Salvo
          casos urgentes o ilegales, te avisaremos antes y podrás descargar tus clips.
        </li>
      </ul>

      <h2>9. Cambios en los términos</h2>
      <p>
        Si modificamos estos términos te avisaremos por email o en la aplicación con al menos 15 días de antelación. Si no
        estás de acuerdo con los cambios, puedes dar de baja tu cuenta antes de que entren en vigor.
      </p>

      <h2>10. Ley aplicable y contacto</h2>
      <p>
        Estos términos se rigen por la ley española. Si eres consumidor, podrás acudir a los tribunales de tu domicilio.
        Para cualquier duda o reclamación, escríbenos a <a href={`mailto:${owner.email}`}>{owner.email}</a>. También
        puedes usar la plataforma europea de resolución de litigios en línea:{" "}
        <a href="https://ec.europa.eu/consumers/odr">ec.europa.eu/consumers/odr</a>.
      </p>
    </article>
  );
}
