import { CheckIcon, CopyIcon, MonitorIcon, ShieldCheckIcon, SmartphoneIcon, SquareIcon } from "lucide-react";

import { CaptionPreview } from "@/components/caption-preview";
import type { CaptionStyle } from "@/lib/api/client";
import { cn } from "@/lib/utils";

const base: CaptionStyle = {
  enabled: true, font: "Archivo Black", text_color: "FFFFFF", highlight_color: "B6E34A", size: "l",
  position: "middle", uppercase: true, box: false, box_color: "000000",
};
const STYLES: { name: string; style: CaptionStyle; words: string[] }[] = [
  { name: "Clásico", style: base, words: ["Mira", "esto"] },
  { name: "Caja", style: { ...base, font: "Poppins", uppercase: false, box: true, highlight_color: "FFE600" },
    words: ["Mira", "esto"] },
  { name: "Titular", style: { ...base, font: "Bebas Neue", highlight_color: "FF3B30" }, words: ["Mira", "esto"] },
];

function Tile({ className, title, text, children }: {
  className?: string;
  title: string;
  text: string;
  children?: React.ReactNode;
}) {
  return (
    <div className={cn("flex flex-col gap-5 overflow-hidden rounded-3xl border bg-card p-6", className)}>
      <div className="flex flex-col gap-1.5">
        <h3 className="text-lg font-semibold tracking-tight">{title}</h3>
        <p className="text-sm text-pretty text-muted-foreground">{text}</p>
      </div>
      {children}
    </div>
  );
}

export function FeatureGrid() {
  return (
    <div className="grid gap-4 md:grid-cols-6">
      <Tile
        className="md:col-span-4"
        title="Subtítulos que retienen"
        text="Seis estilos listos para usar, con la palabra que se está diciendo resaltada. Cambia fuente, colores, tamaño y posición."
      >
        <div className="grid grid-cols-3 gap-3">
          {STYLES.map((s) => (
            <figure key={s.name} className="flex flex-col gap-2">
              <CaptionPreview style={s.style} words={s.words} activeIndex={1} className="rounded-2xl" />
              <figcaption className="text-center text-xs text-muted-foreground">{s.name}</figcaption>
            </figure>
          ))}
        </div>
      </Tile>

      <Tile className="md:col-span-2" title="Editor en el navegador"
            text="Ajusta el inicio y el final, corrige una palabra mal transcrita y vuelve a generar el clip.">
        <div className="mt-auto flex flex-col gap-3 rounded-2xl bg-muted/60 p-4">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Inicio 1:12.4</span>
            <span className="rounded bg-card px-1.5 py-0.5 font-medium text-foreground shadow-xs">34.8 s</span>
            <span>Fin 1:47.2</span>
          </div>
          <div className="relative h-8 rounded-lg bg-card shadow-xs">
            <div className="absolute inset-y-1 right-[18%] left-[22%] rounded-md bg-primary/35 ring-2 ring-primary" />
            <span className="absolute inset-y-0 left-[22%] w-1 -translate-x-1/2 rounded-full bg-brand-ink" />
            <span className="absolute inset-y-0 right-[18%] w-1 translate-x-1/2 rounded-full bg-brand-ink" />
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5 rounded-2xl bg-muted/60 p-4 text-sm">
          {["Hoy", "os", "enseño"].map((w) => (
            <span key={w} className="rounded-md bg-card px-2 py-1 shadow-xs">{w}</span>
          ))}
          <span className="rounded-md bg-brand-soft px-2 py-1 text-brand-ink underline decoration-dotted underline-offset-4">
            SmartCuts
          </span>
          {["paso", "a", "paso"].map((w, i) => (
            <span key={i} className="rounded-md bg-card px-2 py-1 shadow-xs">{w}</span>
          ))}
        </div>
      </Tile>

      <Tile className="md:col-span-2" title="Textos listos para publicar"
            text="Título, descripción y hashtags pensados para TikTok, Reels y Shorts.">
        <div className="mt-auto rounded-2xl bg-muted/60 p-4 text-sm">
          <p>Lo que nadie te cuenta sobre aprender rápido. ¿Te ha pasado?</p>
          <p className="mt-1 text-brand-ink">#aprendizaje #productividad #consejos</p>
          <span className="mt-3 inline-flex items-center gap-1.5 rounded-md bg-card px-2 py-1 text-xs shadow-xs">
            <CopyIcon className="size-3" /> Copiar
          </span>
        </div>
      </Tile>

      <Tile className="md:col-span-2" title="Todos los formatos"
            text="Vertical para TikTok y Reels, cuadrado para el feed y horizontal para YouTube.">
        <div className="mt-auto flex items-end justify-center gap-4 rounded-2xl bg-muted/60 p-4">
          {[
            { icon: SmartphoneIcon, label: "9:16", cls: "h-20 w-11" },
            { icon: SquareIcon, label: "1:1", cls: "size-16" },
            { icon: MonitorIcon, label: "16:9", cls: "h-12 w-20" },
          ].map(({ icon: Icon, label, cls }) => (
            <div key={label} className="flex flex-col items-center gap-2">
              <div className={cn("flex items-center justify-center rounded-lg border-2 border-foreground/80 bg-card", cls)}>
                <Icon className="size-4 text-muted-foreground" />
              </div>
              <span className="text-xs font-medium">{label}</span>
            </div>
          ))}
        </div>
      </Tile>

      <Tile className="md:col-span-2" title="Privacidad de verdad"
            text="Tus vídeos se guardan y procesan en la Unión Europea y nunca se usan para entrenar IA.">
        <ul className="mt-auto flex flex-col gap-2 rounded-2xl bg-muted/60 p-4 text-sm">
          {["Servidores en la UE", "El original se borra cuando tú decides", "Elimina tu cuenta en un clic"].map((t) => (
            <li key={t} className="flex items-center gap-2">
              <CheckIcon className="size-4 text-brand-ink" /> {t}
            </li>
          ))}
          <li className="flex items-center gap-2 text-muted-foreground">
            <ShieldCheckIcon className="size-4" /> Cumple el RGPD
          </li>
        </ul>
      </Tile>
    </div>
  );
}
