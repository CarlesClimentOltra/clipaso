import type { Metadata } from "next";

import { LandingPage } from "@/components/landing/landing-page";
import { I18nProvider } from "@/lib/i18n";
import { landingJsonLd, landingMetadata } from "@/lib/seo";

export const metadata: Metadata = landingMetadata("es");

export default function Home() {
  return (
    <I18nProvider locale="es">
      <script
        type="application/ld+json"
        // Datos estructurados estáticos (sin entrada del usuario).
        dangerouslySetInnerHTML={{ __html: JSON.stringify(landingJsonLd("es")) }}
      />
      <LandingPage />
    </I18nProvider>
  );
}
