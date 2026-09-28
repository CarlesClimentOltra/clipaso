import type { Metadata } from "next";

import { LandingPage } from "@/components/landing/landing-page";
import { I18nProvider } from "@/lib/i18n";
import { landingJsonLd, landingMetadata } from "@/lib/seo";

export const metadata: Metadata = landingMetadata("en");

/** Portada en inglés: URL propia para que los buscadores la indexen por separado. */
export default function HomeEnglish() {
  return (
    <I18nProvider locale="en">
      <script
        type="application/ld+json"
        // Datos estructurados estáticos (sin entrada del usuario).
        dangerouslySetInnerHTML={{ __html: JSON.stringify(landingJsonLd("en")) }}
      />
      <LandingPage />
    </I18nProvider>
  );
}
