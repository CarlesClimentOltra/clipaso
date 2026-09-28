"use client";

import { CheckIcon, CopyIcon, MonitorIcon, ShieldCheckIcon, SmartphoneIcon, SquareIcon } from "lucide-react";

import { CaptionPreview } from "@/components/caption-preview";
import { SAMPLE_STYLES } from "@/components/landing/sample-styles";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const STYLE_IDS = ["clasico", "caja", "titular"];

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
  const { t } = useI18n();
  const f = t.landing.features;
  return (
    <div className="grid gap-4 md:grid-cols-6">
      <Tile
        className="md:col-span-4"
        title={f.captionsTitle}
        text={f.captionsText}
      >
        <div className="grid grid-cols-3 gap-3">
          {STYLE_IDS.map((id) => (
            <figure key={id} className="flex flex-col gap-2">
              <CaptionPreview style={SAMPLE_STYLES[id]} words={f.captionWords} activeIndex={1} className="rounded-2xl" />
              <figcaption className="text-center text-xs text-muted-foreground">{t.styles.presets[id]}</figcaption>
            </figure>
          ))}
        </div>
      </Tile>

      <Tile className="md:col-span-2" title={f.editorTitle} text={f.editorText}>
        <div className="mt-auto flex flex-col gap-3 rounded-2xl bg-muted/60 p-4">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{f.editorStart} 1:12.4</span>
            <span className="rounded bg-card px-1.5 py-0.5 font-medium text-foreground shadow-xs">34.8 s</span>
            <span>{f.editorEnd} 1:47.2</span>
          </div>
          <div className="relative h-8 rounded-lg bg-card shadow-xs">
            <div className="absolute inset-y-1 right-[18%] left-[22%] rounded-md bg-primary/35 ring-2 ring-primary" />
            <span className="absolute inset-y-0 left-[22%] w-1 -translate-x-1/2 rounded-full bg-brand-ink" />
            <span className="absolute inset-y-0 right-[18%] w-1 translate-x-1/2 rounded-full bg-brand-ink" />
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5 rounded-2xl bg-muted/60 p-4 text-sm">
          {f.editorWords.map((w) => (
            <span key={w} className="rounded-md bg-card px-2 py-1 shadow-xs">{w}</span>
          ))}
          <span className="rounded-md bg-brand-soft px-2 py-1 text-brand-ink underline decoration-dotted underline-offset-4">
            {f.editorFixed}
          </span>
          {f.editorTail.map((w, i) => (
            <span key={i} className="rounded-md bg-card px-2 py-1 shadow-xs">{w}</span>
          ))}
        </div>
      </Tile>

      <Tile className="md:col-span-2" title={f.textsTitle} text={f.textsText}>
        <div className="mt-auto rounded-2xl bg-muted/60 p-4 text-sm">
          <p>{f.textsSample}</p>
          <p className="mt-1 text-brand-ink">{f.textsTags}</p>
          <span className="mt-3 inline-flex items-center gap-1.5 rounded-md bg-card px-2 py-1 text-xs shadow-xs">
            <CopyIcon className="size-3" /> {t.common.copy}
          </span>
        </div>
      </Tile>

      <Tile className="md:col-span-2" title={f.formatsTitle} text={f.formatsText}>
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

      <Tile className="md:col-span-2" title={f.privacyTitle} text={f.privacyText}>
        <ul className="mt-auto flex flex-col gap-2 rounded-2xl bg-muted/60 p-4 text-sm">
          {f.privacyItems.map((item) => (
            <li key={item} className="flex items-center gap-2">
              <CheckIcon className="size-4 text-brand-ink" /> {item}
            </li>
          ))}
          <li className="flex items-center gap-2 text-muted-foreground">
            <ShieldCheckIcon className="size-4" /> {f.gdpr}
          </li>
        </ul>
      </Tile>
    </div>
  );
}
