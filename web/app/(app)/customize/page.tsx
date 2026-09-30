"use client";

import { BrandSettings } from "@/components/brand-settings";
import { CaptionStylesSettings } from "@/components/caption-styles-settings";
import { PageHeader } from "@/components/page-header";
import { useI18n } from "@/lib/i18n";

/** Personalizar: tus estilos de subtítulos y tu marca personal (separado de los ajustes de la cuenta). */
export default function CustomizePage() {
  const { t } = useI18n();
  const c = t.customize;
  return (
    <div className="flex max-w-5xl flex-col gap-6">
      <PageHeader eyebrow={c.eyebrow} title={c.title} description={c.lead} />
      <CaptionStylesSettings />
      <BrandSettings />
    </div>
  );
}
