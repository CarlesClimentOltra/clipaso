"use client";

import {
  CaptionsIcon,
  CropIcon,
  DownloadIcon,
  PaletteIcon,
  ScissorsIcon,
  ShieldCheckIcon,
  SparklesIcon,
  ZapIcon,
  type LucideIcon,
} from "lucide-react";

import { useI18n } from "@/lib/i18n";

const ICONS: LucideIcon[] = [
  SparklesIcon, CaptionsIcon, CropIcon, ScissorsIcon, PaletteIcon, DownloadIcon, ZapIcon, ShieldCheckIcon,
];

function Row({ hidden }: { hidden?: boolean }) {
  const { t } = useI18n();
  const items = t.landing.marquee.map(([title, text], i) => ({ icon: ICONS[i], title, text }));
  return (
    <ul className="flex shrink-0 items-center gap-14 pr-14" aria-hidden={hidden || undefined}>
      {items.map(({ icon: Icon, title, text }) => (
        <li key={title} className="flex items-center gap-3 whitespace-nowrap">
          <Icon className="size-5 text-brand-ink" aria-hidden="true" />
          <span className="flex flex-col leading-tight">
            <span className="font-medium">{title}</span>
            <span className="text-sm text-muted-foreground">{text}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Cinta de ventajas en bucle: la lista va duplicada para que el desplazamiento no tenga saltos. */
export function FeatureMarquee() {
  const { t } = useI18n();
  return (
    <section aria-label={t.landing.marqueeLabel} className="marquee overflow-hidden border-y py-6">
      <div className="marquee-track flex w-max">
        <Row />
        <Row hidden />
      </div>
    </section>
  );
}
