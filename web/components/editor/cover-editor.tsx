"use client";

import { DownloadIcon, ImageIcon, Loader2Icon, SparklesIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { ApiError, type Clip, type ClipCover, type CoverInput } from "@/lib/api/client";
import { useCoverActions } from "@/lib/api/hooks";
import { formatTime } from "@/lib/captions";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type Template = ClipCover["template"];
// «limpia» (sin texto) no es una tarjeta más: se elige con el interruptor «Texto encima».
const TEXT_TEMPLATES: Template[] = ["impacto", "caja", "titular"];

/**
 * Dibuja fotogramas del vídeo ligero del editor en canvas (solo para elegir: la portada final se
 * compone en el servidor con el fotograma a resolución completa).
 */
function useFrames(src: string | null, times: number[]) {
  const canvases = useRef<(HTMLCanvasElement | null)[]>([]);
  const key = times.map((t) => t.toFixed(2)).join(",");
  useEffect(() => {
    if (!src || !times.length) return;
    let cancelled = false;
    const video = document.createElement("video");
    video.muted = true;
    video.playsInline = true;
    video.preload = "auto";
    video.src = src;
    const wait = (event: string, ms: number) =>
      new Promise<void>((resolve) => {
        const timer = window.setTimeout(resolve, ms);
        video.addEventListener(event, () => {
          window.clearTimeout(timer);
          resolve();
        }, { once: true });
      });
    (async () => {
      await wait("loadeddata", 15000);
      for (let i = 0; i < times.length && !cancelled; i++) {
        const seeked = wait("seeked", 3000);
        video.currentTime = times[i];
        await seeked;
        const canvas = canvases.current[i];
        const ctx = canvas?.getContext("2d");
        if (!canvas || !ctx || !video.videoWidth) continue;
        const scale = Math.max(canvas.width / video.videoWidth, canvas.height / video.videoHeight);
        const w = video.videoWidth * scale;
        const h = video.videoHeight * scale;
        ctx.drawImage(video, (canvas.width - w) / 2, (canvas.height - h) / 2, w, h);
      }
    })();
    return () => {
      cancelled = true;
      video.removeAttribute("src");
      video.load();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [src, key]);
  // Cada canvas se registra por su posición en `times`.
  return (i: number) => (el: HTMLCanvasElement | null) => {
    canvases.current[i] = el;
  };
}

function Preview({ url, downloadUrl, label, className }: { url: string; downloadUrl: string; label: string; className?: string }) {
  return (
    <figure className={cn("flex flex-col gap-2", className)}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={url} alt={label} className="w-full rounded-xl border bg-muted object-cover shadow-sm" />
      <figcaption className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>{label}</span>
        <a href={downloadUrl} download className={buttonVariants({ variant: "ghost", size: "sm" })}>
          <DownloadIcon /> JPG
        </a>
      </figcaption>
    </figure>
  );
}

/** Pestaña «Portada» del editor. */
export function CoverEditor({
  clip,
  jobId,
  previewUrl,
  canChangeFrame,
  frameMessage,
  large = false,
}: {
  clip: Clip;
  jobId: string;
  previewUrl: string | null;
  canChangeFrame: boolean;
  /** Qué decir cuando aquí no se puede cambiar el fotograma. */
  frameMessage?: string;
  /** Vista grande (pantalla de una miniatura): la 16:9 en grande y la 9:16 al lado. */
  large?: boolean;
}) {
  const { t } = useI18n();
  const c = t.cover;
  const cover = clip.cover!;
  const actions = useCoverActions(jobId, clip.id);
  const [text, setText] = useState(cover.text);
  const [highlight, setHighlight] = useState<number | null>(cover.highlight ?? null);
  const [template, setTemplate] = useState<Template>(cover.template);
  const [time, setTime] = useState(cover.time);
  const [lastTextTemplate, setLastTextTemplate] = useState<Template>(
    cover.template === "limpia" ? "impacto" : cover.template);
  const [seen, setSeen] = useState(cover);
  // Si llega una portada nueva (otra propuesta de la IA), el formulario se pone al día.
  if (seen !== cover) {
    setSeen(cover);
    setText(cover.text);
    setHighlight(cover.highlight ?? null);
    setTemplate(cover.template);
    setTime(cover.time);
  }

  const candidates = Array.from(new Set([cover.time, ...cover.candidates].map((x) => Math.round(x * 100) / 100)))
    .sort((a, b) => a - b);
  // Miniaturas hechas sin subir el vídeo: los fotogramas propuestos están guardados como imágenes.
  const imageAt = new Map(cover.candidates.map((ct, i) => [Math.round(ct * 100) / 100,
                                                            cover.candidate_images?.[i] ?? null]));
  const hasImages = [...imageAt.values()].some(Boolean);
  const canPickFrame = canChangeFrame || hasImages;
  const frames = useFrames(hasImages ? null : previewUrl, candidates);
  // El fotograma elegido con la barra se dibuja cuando se deja de arrastrar.
  const [shownTime, setShownTime] = useState(time);
  useEffect(() => {
    const id = window.setTimeout(() => setShownTime(time), 250);
    return () => window.clearTimeout(id);
  }, [time]);
  const custom = useFrames(previewUrl, candidates.includes(shownTime) ? [] : [shownTime]);
  const textOn = template !== "limpia";
  const words = text.split(/\s+/).filter(Boolean);
  const dirty = text.trim() !== cover.text || (highlight ?? null) !== (cover.highlight ?? null)
    || template !== cover.template || Math.abs(time - cover.time) > 0.05;
  const busy = actions.save.isPending || cover.pending || actions.regenerate.isPending;

  async function save(templateOverride?: Template) {
    const body: CoverInput = {};
    const nextTemplate = templateOverride ?? template;
    if (text.trim() !== cover.text && text.trim()) body.text = text.trim();
    if ((highlight ?? null) !== (cover.highlight ?? null)) body.highlight = highlight ?? -1;
    if (nextTemplate !== cover.template) body.template = nextTemplate;
    if (Math.abs(time - cover.time) > 0.05) body.time = time;
    try {
      await actions.save.mutateAsync(body);
      toast.success(c.saved);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : c.error);
    }
  }

  async function regenerate() {
    try {
      await actions.regenerate.mutateAsync();
      toast.info(c.regenerating);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : c.error);
    }
  }

  /** El interruptor aplica al momento: con texto o imagen limpia. */
  function toggleText(on: boolean) {
    const next = on ? lastTextTemplate : "limpia";
    if (!on) setLastTextTemplate(template === "limpia" ? lastTextTemplate : template);
    setTemplate(next);
    save(next);
  }

  return (
    <div className="flex flex-col gap-6">
      {!large && <p className="text-xs text-muted-foreground">{c.lead}</p>}

      <div className={cn("relative grid gap-4",
                         large ? "lg:grid-cols-[1fr_220px]" : "sm:grid-cols-[minmax(0,180px)_1fr]")}>
        {large ? (
          <>
            <Preview url={cover.horizontal_url} downloadUrl={cover.horizontal_download_url} label={c.horizontal}
                     className="self-start" />
            <Preview url={cover.vertical_url} downloadUrl={cover.vertical_download_url} label={c.vertical}
                     className="mx-auto w-full max-w-[220px]" />
          </>
        ) : (
          <>
            <Preview url={cover.vertical_url} downloadUrl={cover.vertical_download_url} label={c.vertical} />
            <Preview url={cover.horizontal_url} downloadUrl={cover.horizontal_download_url} label={c.horizontal}
                     className="self-start" />
          </>
        )}
        {busy && (
          <div className="absolute inset-0 flex items-center justify-center gap-2 rounded-xl bg-background/70 text-sm backdrop-blur-sm">
            <Loader2Icon className="size-4 animate-spin" /> {cover.pending ? c.aiWorking : c.applying}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between gap-4 rounded-xl border bg-muted/40 p-4">
        <div>
          <Label htmlFor="cover-text-on" className="text-base">{c.textOn}</Label>
          <p className="text-xs text-muted-foreground">{textOn ? c.textOnHint : c.textOffHint}</p>
        </div>
        <Switch id="cover-text-on" checked={textOn} disabled={busy} onCheckedChange={(v: boolean) => toggleText(v)} />
      </div>

      {textOn && (
      <div className="flex flex-col gap-2">
        <Label htmlFor="cover-text">{c.text}</Label>
        <Input id="cover-text" value={text} maxLength={42} disabled={busy} onChange={(e) => {
          setText(e.target.value);
          setHighlight(null);
        }} />
        {words.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-muted-foreground">{c.highlight}</span>
            {words.map((w, i) => (
              <button
                key={`${i}-${w}`}
                type="button"
                disabled={busy}
                aria-pressed={highlight === i}
                onClick={() => setHighlight(highlight === i ? null : i)}
                className={cn(
                  "rounded-md border px-2 py-0.5 text-xs outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                  highlight === i ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted",
                )}
              >
                {w}
              </button>
            ))}
          </div>
        )}
      </div>
      )}

      {textOn && (
      <div className="flex flex-col gap-2">
        <Label>{c.template}</Label>
        <div className="grid grid-cols-3 gap-2" role="radiogroup" aria-label={c.template}>
          {TEXT_TEMPLATES.map((tpl) => (
            <button
              key={tpl}
              type="button"
              role="radio"
              aria-checked={template === tpl}
              disabled={busy}
              onClick={() => setTemplate(tpl)}
              className={cn(
                "flex flex-col gap-0.5 rounded-xl border p-2.5 text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                template === tpl ? "border-primary bg-primary/10 ring-1 ring-primary" : "hover:bg-muted/60",
              )}
            >
              <span className="text-sm font-medium">{c.templates[tpl][0]}</span>
              <span className="text-xs leading-snug text-muted-foreground">{c.templates[tpl][1]}</span>
            </button>
          ))}
        </div>
      </div>
      )}

      <div className="flex flex-col gap-2">
        <Label>{c.frame}</Label>
        {canPickFrame ? (
          <>
            <div className="flex gap-2 overflow-x-auto pb-1" role="radiogroup" aria-label={c.frame}>
              {candidates.map((ct, i) => (
                <button
                  key={ct}
                  type="button"
                  role="radio"
                  aria-checked={Math.abs(time - ct) < 0.05}
                  aria-label={formatTime(ct)}
                  disabled={busy}
                  onClick={() => setTime(ct)}
                  className={cn(
                    "relative shrink-0 overflow-hidden rounded-lg outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                    Math.abs(time - ct) < 0.05 ? "ring-2 ring-primary" : "opacity-80 hover:opacity-100",
                  )}
                >
                  {imageAt.get(ct) ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={imageAt.get(ct)!} alt="" className="h-20 w-36 bg-muted object-cover" />
                  ) : (
                    <canvas ref={frames(i)} width={72} height={128} className="h-24 w-[54px] bg-muted object-cover" />
                  )}
                  <span className="absolute inset-x-0 bottom-0 bg-black/55 text-[10px] text-white tabular-nums">
                    {formatTime(ct)}
                  </span>
                </button>
              ))}
              {!candidates.includes(time) && (
                <div className="relative shrink-0 overflow-hidden rounded-lg ring-2 ring-primary">
                  <canvas ref={custom(0)} width={72} height={128}
                          className="h-24 w-[54px] bg-muted" />
                  <span className="absolute inset-x-0 bottom-0 bg-black/55 text-[10px] text-white tabular-nums">
                    {formatTime(time)}
                  </span>
                </div>
              )}
            </div>
            {canChangeFrame && previewUrl && (
            <div className="flex items-center gap-3">
              <span className="shrink-0 text-xs text-muted-foreground">{c.otherMoment}</span>
              <Slider
                aria-label={c.otherMoment}
                value={[time]}
                min={clip.start}
                max={clip.end}
                step={0.1}
                disabled={busy}
                onValueChange={(v: number | readonly number[]) => setTime(Array.isArray(v) ? v[0] : (v as number))}
              />
              <span className="w-10 shrink-0 text-right text-xs tabular-nums">{formatTime(time)}</span>
            </div>
            )}
          </>
        ) : (
          <p className="text-xs text-muted-foreground">{frameMessage ?? c.noSource}</p>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" onClick={() => save()} disabled={!dirty || busy || !text.trim() && textOn}>
          {actions.save.isPending ? <Loader2Icon className="animate-spin" /> : <ImageIcon />} {c.apply}
        </Button>
        {canPickFrame && (
          <Button type="button" variant="outline" onClick={regenerate} disabled={busy}>
            <SparklesIcon /> {c.regenerate}
          </Button>
        )}
      </div>
    </div>
  );
}
