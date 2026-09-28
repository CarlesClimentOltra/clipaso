"use client";

import { useI18n } from "@/lib/i18n";

/** Los textos legales solo existen en español (la ley aplicable es la española); se avisa a quien usa la web en inglés. */
export function LegalLanguageNote() {
  const { t } = useI18n();
  if (!t.legalNote) return null;
  return <p className="mb-6 rounded-xl bg-muted px-4 py-3 text-sm text-muted-foreground">{t.legalNote}</p>;
}
