import type { Metadata } from "next";
import Link from "next/link";

import { legal } from "@/lib/legal";

export const metadata: Metadata = { title: "Política de privacidad · SmartCuts" };

export default function PrivacyPage() {
  const { owner } = legal;
  return (
    <article>
      <h1>Política de privacidad</h1>
      <p className="updated">Última actualización: {legal.updatedAt}</p>

      <p>
        Esta política explica qué datos personales trata SmartCuts cuando usas la web y el servicio, para qué, durante
        cuánto tiempo y qué derechos tienes. Está redactada conforme al Reglamento General de Protección de Datos (RGPD)
        y a la Ley Orgánica 3/2018 de Protección de Datos (LOPDGDD).
      </p>

      <h2>1. Responsable del tratamiento</h2>
      <ul>
        <li>Titular: {owner.name}</li>
        <li>NIF: {owner.taxId}</li>
        <li>Domicilio: {owner.address}</li>
        <li>
          Contacto para privacidad: <a href={`mailto:${owner.email}`}>{owner.email}</a>
        </li>
      </ul>

      <h2>2. Qué datos tratamos</h2>
      <ul>
        <li>
          <strong>Datos de tu cuenta:</strong> email y contraseña. La contraseña se guarda cifrada y nunca la vemos. Si
          eliges «Continuar con Google», Google nos facilita tu email y tu nombre, y no creamos contraseña salvo que la
          añadas tú; Google trata tus datos según su propia política de privacidad.
        </li>
        <li>
          <strong>Los vídeos que subes</strong> y lo que generamos a partir de ellos: el audio, su transcripción, los
          clips, las miniaturas, los títulos y las descripciones de cada clip. Si en tus vídeos aparecen o hablan otras
          personas, también tratamos su imagen y su voz por cuenta tuya (ver apartado 8).
        </li>
        <li>
          <strong>Datos de uso:</strong> minutos consumidos, plan contratado, fechas de los proyectos y su estado.
        </li>
        <li>
          <strong>Datos técnicos:</strong> dirección IP, tipo de navegador y registros de errores, necesarios para que
          el servicio funcione y sea seguro.
        </li>
      </ul>
      <p>No tratamos categorías especiales de datos de forma intencionada ni usamos tus vídeos para fines publicitarios.</p>

      <h2>3. Para qué los usamos y con qué base legal</h2>
      <div className="overflow-x-auto">
        <table>
          <thead>
            <tr>
              <th>Finalidad</th>
              <th>Base legal</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Crear y gestionar tu cuenta, procesar tus vídeos y entregarte los clips</td>
              <td>Ejecución del contrato (art. 6.1.b RGPD)</td>
            </tr>
            <tr>
              <td>Enviarte emails sobre tu cuenta y tus vídeos (confirmación de registro, clips listos o fallos)</td>
              <td>Ejecución del contrato (art. 6.1.b RGPD)</td>
            </tr>
            <tr>
              <td>Controlar el consumo de minutos de tu plan</td>
              <td>Ejecución del contrato (art. 6.1.b RGPD)</td>
            </tr>
            <tr>
              <td>Detectar errores, prevenir abusos y mantener la seguridad del servicio</td>
              <td>Interés legítimo en un servicio fiable y seguro (art. 6.1.f RGPD)</td>
            </tr>
            <tr>
              <td>Cumplir obligaciones legales (por ejemplo, fiscales si contratas un plan de pago)</td>
              <td>Obligación legal (art. 6.1.c RGPD)</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p>
        <strong>No usamos tus vídeos ni sus transcripciones para entrenar modelos de inteligencia artificial</strong>, ni
        los compartimos con nadie salvo con los proveedores necesarios para prestar el servicio (apartado 5). Tampoco
        enviamos publicidad.
      </p>

      <h2>4. Decisiones automatizadas</h2>
      <p>
        SmartCuts usa inteligencia artificial para transcribir tus vídeos y proponer los fragmentos con más potencial.
        Es una herramienta de edición: no toma decisiones que produzcan efectos jurídicos sobre ti ni te afecten de forma
        significativa. Tú decides qué clips usar y dónde publicarlos.
      </p>

      <h2>5. Proveedores que tratan datos por nuestra cuenta</h2>
      <p>
        Para prestar el servicio usamos estos proveedores (encargados del tratamiento), con los que tenemos firmados los
        contratos que exige el RGPD. Solo acceden a los datos necesarios para su función:
      </p>
      <div className="overflow-x-auto">
        <table>
          <thead>
            <tr>
              <th>Proveedor</th>
              <th>Función</th>
              <th>Dónde se tratan los datos</th>
            </tr>
          </thead>
          <tbody>
            {legal.processors.map((p) => (
              <tr key={p.name}>
                <td>
                  {p.name}
                  <br />
                  <span className="text-muted-foreground">{p.company}</span>
                </td>
                <td>{p.role}</td>
                <td>{p.location}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>6. Transferencias internacionales</h2>
      <p>
        Alojamos los datos en la Unión Europea siempre que es posible: tus vídeos, clips y cuenta se guardan en la UE, y
        el procesamiento de vídeo se hace en servidores de la UE. Aun así, varios proveedores son empresas con sede en
        Estados Unidos, y uno de ellos, Anthropic, trata en EE. UU. el <strong>texto transcrito</strong> de tus vídeos
        para seleccionar los mejores momentos (no recibe el vídeo ni tu email). Anthropic no usa estos datos para entrenar
        sus modelos y solo los conserva durante un plazo limitado.
      </p>
      <p>
        Estas transferencias se amparan en el Marco de Privacidad de Datos UE-EE. UU. cuando el proveedor está adherido y,
        en todo caso, en las cláusulas contractuales tipo aprobadas por la Comisión Europea (art. 46 RGPD).
      </p>

      <h2>7. Cuánto tiempo conservamos los datos</h2>
      <ul>
        <li>
          <strong>Vídeo original:</strong> se borra en cuanto termina el procesamiento. Si una subida no llega a
          procesarse, se borra en un máximo de 24 horas.
        </li>
        <li>
          <strong>Audio y transcripción:</strong> son archivos temporales que se eliminan al terminar cada vídeo.
        </li>
        <li>
          <strong>Clips y miniaturas:</strong> durante el tiempo que indica tu plan (7 días en el plan Gratis, 30 en
          Creator y 60 en Pro). Después se borran automáticamente; el proyecto queda en tu historial como «caducado»,
          solo con su título y fechas.
        </li>
        <li>
          <strong>Cuenta e historial:</strong> mientras mantengas la cuenta. Puedes eliminarla tú mismo en cualquier
          momento desde «Mi cuenta»: se borran al instante tu cuenta, tus proyectos, tus clips y tu historial de consumo.
          Las copias de seguridad de la base de datos pueden conservarlos hasta 30 días más, hasta que se renuevan.
        </li>
        <li>
          <strong>Registro de consumo y facturación:</strong> el tiempo que exija la ley (por ejemplo, 6 años para la
          documentación contable y fiscal si has contratado un plan de pago).
        </li>
        <li>
          <strong>Registros técnicos y de errores:</strong> un máximo de 90 días.
        </li>
      </ul>

      <h2>8. Personas que aparecen en tus vídeos</h2>
      <p>
        Si subes vídeos en los que aparecen o hablan otras personas, eres tú quien decide tratar esos datos y debes contar
        con una base legal para ello (por ejemplo, su consentimiento para grabarlas y publicar los clips). En ese caso,
        SmartCuts actúa como encargado del tratamiento por cuenta tuya y trata esos datos solo para generar tus clips,
        conforme a los <Link href="/legal/terminos">Términos del servicio</Link>.
      </p>

      <h2>9. Tus derechos</h2>
      <p>Puedes ejercer en cualquier momento, sin coste, estos derechos:</p>
      <ul>
        <li>Acceder a tus datos y obtener una copia.</li>
        <li>Rectificar los datos inexactos.</li>
        <li>Suprimir tus datos y tu cuenta.</li>
        <li>Oponerte al tratamiento o pedir que se limite.</li>
        <li>Portabilidad: recibir tus datos en un formato estructurado y de uso común.</li>
      </ul>
      <p>
        Escríbenos a <a href={`mailto:${owner.email}`}>{owner.email}</a> desde el email de tu cuenta indicando qué derecho
        quieres ejercer. Te responderemos en un plazo máximo de un mes. Además, puedes borrar proyectos y clips, o
        eliminar tu cuenta con todos sus datos, en cualquier momento desde la propia aplicación («Mi cuenta»).
      </p>
      <p>
        Si consideras que no hemos atendido correctamente tu solicitud, puedes presentar una reclamación ante la Agencia
        Española de Protección de Datos (<a href="https://www.aepd.es">www.aepd.es</a>).
      </p>

      <h2>10. Seguridad</h2>
      <p>
        Las comunicaciones van cifradas (HTTPS), las contraseñas se guardan cifradas, el acceso a los archivos se hace con
        enlaces firmados que caducan y cada usuario solo puede ver sus propios proyectos.
      </p>

      <h2>11. Menores</h2>
      <p>SmartCuts está dirigido a mayores de {legal.minAge} años. No creamos cuentas a sabiendas a menores de esa edad.</p>

      <h2>12. Cambios en esta política</h2>
      <p>
        Si cambiamos esta política de forma relevante te avisaremos por email o en la aplicación antes de que el cambio
        tenga efecto. La fecha de la última actualización figura al principio.
      </p>
    </article>
  );
}
