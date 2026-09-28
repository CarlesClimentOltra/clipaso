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

const ITEMS: { icon: LucideIcon; title: string; text: string }[] = [
  { icon: SparklesIcon, title: "IA que elige", text: "Los mejores momentos" },
  { icon: CaptionsIcon, title: "Subtítulos automáticos", text: "Palabra a palabra" },
  { icon: CropIcon, title: "Reencuadre 9:16", text: "Sigue a quien habla" },
  { icon: ScissorsIcon, title: "Editor integrado", text: "Corrige en segundos" },
  { icon: PaletteIcon, title: "Tu marca", text: "Logo y @usuario" },
  { icon: DownloadIcon, title: "Todo en un ZIP", text: "MP4, SRT y textos" },
  { icon: ZapIcon, title: "Listo en minutos", text: "Sin editar a mano" },
  { icon: ShieldCheckIcon, title: "Datos en la UE", text: "Privacidad RGPD" },
];

function Row({ hidden }: { hidden?: boolean }) {
  return (
    <ul className="flex shrink-0 items-center gap-14 pr-14" aria-hidden={hidden || undefined}>
      {ITEMS.map(({ icon: Icon, title, text }) => (
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
  return (
    <section aria-label="Ventajas de SmartCuts" className="marquee overflow-hidden border-y py-6">
      <div className="marquee-track flex w-max">
        <Row />
        <Row hidden />
      </div>
    </section>
  );
}
