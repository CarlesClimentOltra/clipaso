"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { CheckIcon, FileVideoIcon, UploadCloudIcon, XIcon } from "lucide-react";
import { useEffect, useRef, useState, type DragEvent } from "react";
import { toast } from "sonner";

import type { ClipFormat } from "@/components/caption-preview";
import { PlansLink } from "@/components/error-toast";
import { AudiogramOptions } from "@/components/audiogram-options";
import { ProjectOptions, type ProjectOptionsValue } from "@/components/project-options";
import { ReframeFitPicker } from "@/components/reframe-fit-picker";
import { Segmented } from "@/components/segmented";
import { TrimSelector, type TrimRange } from "@/components/trim-selector";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Switch } from "@/components/ui/switch";
import { ApiError, type Me } from "@/lib/api/client";
import { useApi, useClipOptions, useCreateProject, usePreferences } from "@/lib/api/hooks";
import { discardUpload, type UploadProgress } from "@/lib/api/multipart-upload";
import { useI18n } from "@/lib/i18n";
import { AUDIO_MODES, type VideoMode } from "@/lib/modes";
import { MAX_CLIENT_TRIM_BYTES, preloadTrimmer, trimVideo } from "@/lib/trim";
import { cn } from "@/lib/utils";

const ACCEPT = [".mp4", ".mov", ".mkv", ".webm", ".m4v"];
// Audiograma y «del vídeo al texto» también aceptan audio suelto.
const AUDIO_ACCEPT = [".mp3", ".m4a", ".wav", ".ogg", ".opus", ".aac", ".flac"];
const LANGUAGES = ["es", "en", "pt", "fr", "it", "de", "auto"];
const SUBTITLE_LANGUAGES = ["es", "en", "pt", "fr", "it", "de", "ca"];

type Phase = "idle" | "trimming" | "uploading" | "checking" | "starting";

const LARGE_FILE = 1024 ** 3; // a partir de 1 GB avisamos de que la subida puede tardar

function formatBytes(bytes: number): string {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
  return `${Math.max(1, Math.round(bytes / 1024 ** 2))} MB`;
}

function formatDuration(seconds: number, lessThanMinute: string): string {
  if (seconds < 60) return lessThanMinute;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
}

function formatSpeed(bytesPerSecond: number): string {
  const mbps = (bytesPerSecond * 8) / 1e6;
  return `${mbps >= 10 ? Math.round(mbps) : mbps.toFixed(1)} Mbit/s`;
}

/** Subir y configurar un proyecto de un modo que ya se eligió en «Nuevo proyecto». */
export function UploadForm({ me, mode }: { me: Me; mode: VideoMode }) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fileUrl, setFileUrl] = useState<string | null>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const [sourceFrame, setSourceFrame] = useState<ClipFormat>("horizontal");
  // Más de 1080p (2.7K, 4K…): cuenta el doble de minutos (procesarlo cuesta mucho más).
  const [highRes, setHighRes] = useState(false);
  const [trim, setTrim] = useState<TrimRange | null>(null);
  const [trimProgress, setTrimProgress] = useState(0);
  const uploadingRef = useRef<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [maxClips, setMaxClips] = useState(Math.min(3, me.plan.max_clips_per_job));
  const [languageChoice, setLanguage] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [optionsDraft, setOptionsDraft] = useState<Omit<ProjectOptionsValue, "caption_style"> & {
    caption_style: ProjectOptionsValue["caption_style"] | null;
  }>({
    // Con el vídeo entero, por defecto se respeta su formato; los clips, en vertical.
    mode, subtitle_language: null, format: ["clips", "reframe", "trailer"].includes(mode) ? "vertical" : "original", duration: "auto", topic: "",
    keep_source: true, branding: true, caption_style: null, clean_pace: "normal", clean_fillers: true,
    reframe_fit: "auto", trailer_seconds: 60, audiogram_title: "", audiogram_color: "0F172A",
    audiogram_accent: "B6E34A",
  });
  const cleanMode = mode === "clean";
  // El resultado es el vídeo entero (solo subtitular o sin silencios).
  const reframeMode = mode === "reframe";
  const trailerMode = mode === "trailer";
  const audiogramMode = mode === "audiogram";
  const textMode = mode === "text";
  const accept = AUDIO_MODES.includes(mode) ? [...ACCEPT, ...AUDIO_ACCEPT] : ACCEPT;
  const [audiogramImage, setAudiogramImage] = useState<string | null>(null);
  const subtitleMode = mode === "subtitle" || cleanMode || reframeMode || trailerMode || audiogramMode || textMode;
  const { data: prefs } = usePreferences();
  const { data: catalog } = useClipOptions();
  // Hasta que el usuario toque el estilo, se usa el suyo por defecto (o el primero del catálogo). Los subtítulos
  // van desactivados salvo en «Solo subtitular», donde son el propio modo.
  const baseStyle = prefs?.caption_style ?? catalog?.presets[0]?.style ?? null;
  const defaultStyle = baseStyle && { ...baseStyle, enabled: mode === "subtitle" };
  const options: ProjectOptionsValue | null =
    optionsDraft.caption_style ?? defaultStyle
      ? { ...optionsDraft, caption_style: (optionsDraft.caption_style ?? defaultStyle)! }
      : null;
  const subtitlesOn = mode === "subtitle" || options?.caption_style.enabled === true;
  // Sin subtítulos no hay nada que traducir.
  const toSend = options && { ...options, subtitle_language: subtitlesOn ? options.subtitle_language : null };
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const cancelledRef = useRef(false);
  const { t, locale } = useI18n();
  const u = t.upload;
  const create = useCreateProject();
  const api = useApi();

  // Por defecto, el idioma del vídeo es el de la interfaz.
  const language = languageChoice ?? locale;
  const busy = phase !== "idle";
  const outOfMinutes = me.usage.remaining_minutes <= 0;
  const maxBytes = me.plan.max_upload_mb * 1024 * 1024;
  const maxSeconds = me.plan.max_video_minutes * 60;
  const partial = !!(file && duration && trim && (trim.start > 0.5 || trim.end < duration - 0.5));
  const selectedSeconds = duration ? (partial ? trim!.end - trim!.start : duration) : 0;
  // Lo que ocupará lo que se sube: el tramo (si se recorta en el navegador) o el archivo entero.
  const estimatedBytes = file && duration ? (file.size * selectedSeconds) / duration : file?.size ?? 0;
  const tooLong = !!duration && selectedSeconds > maxSeconds + 0.5;
  const tooBig = !!file && (partial ? estimatedBytes > maxBytes : file.size > maxBytes);

  // El vídeo elegido se previsualiza en local (sin subir nada); la URL se libera al cambiarlo o al salir.
  useEffect(() => () => {
    if (fileUrl) URL.revokeObjectURL(fileUrl);
  }, [fileUrl]);

  // En cuanto se elige un tramo, se descarga el recortador para que al pulsar «Crear» sea inmediato.
  useEffect(() => {
    if (partial) preloadTrimmer();
  }, [partial]);

  function pick(candidate: File | undefined) {
    setFileError(null);
    if (!candidate) return;
    const ext = candidate.name.slice(candidate.name.lastIndexOf(".")).toLowerCase();
    if (!accept.includes(ext)) {
      setFileError(AUDIO_MODES.includes(mode) ? u.formatErrorAudio : u.formatError);
      return;
    }
    // Un archivo más grande que el máximo se admite si luego se elige un tramo que sí quepa.
    setFile(candidate);
    setFileUrl(URL.createObjectURL(candidate));
    setDuration(null);
    setTrim(null);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (!busy) pick(e.dataTransfer.files?.[0]);
  }

  /** El archivo a subir: el tramo recortado en el navegador o, si no se puede, el original + tramo para el servidor. */
  async function prepare(): Promise<{ upload: File; serverTrim: TrimRange | null } | null> {
    if (!file) return null;
    if (!partial || !trim) return { upload: file, serverTrim: null };
    if (estimatedBytes <= MAX_CLIENT_TRIM_BYTES) {
      setPhase("trimming");
      setTrimProgress(0);
      try {
        return { upload: await trimVideo(file, trim.start, trim.end, setTrimProgress), serverTrim: null };
      } catch (err) {
        console.warn("No se pudo recortar en el navegador; se recortará en el servidor.", err);
      }
    }
    if (file.size > maxBytes) {
      toast.error(u.trimFailedBig);
      return null;
    }
    return { upload: file, serverTrim: trim };
  }

  async function submit() {
    if (!file) return;
    abortRef.current = new AbortController();
    cancelledRef.current = false;
    setProgress(null);
    try {
      const prepared = await prepare();
      if (!prepared) {
        setPhase("idle");
        return;
      }
      uploadingRef.current = prepared.upload;
      const job = await create.mutateAsync({
        file: prepared.upload,
        trim: prepared.serverTrim,
        maxClips: subtitleMode ? 1 : maxClips,
        language,
        options: toSend ?? { ...optionsDraft, caption_style: null },
        audiogramImage: audiogramMode ? audiogramImage : null,
        onUploadProgress: setProgress,
        onPhase: setPhase,
        signal: abortRef.current.signal,
      });
      toast.success(u.received);
      router.push(`/projects/${job.id}`);
    } catch (err) {
      setPhase("idle");
      if (cancelledRef.current) return;
      const interrupted = err instanceof ApiError && ["network_error", "part_failed"].includes(err.code);
      toast.error(
        interrupted
          ? u.interrupted
          : err instanceof ApiError
            ? err.message
            : t.common.genericError,
      );
    }
  }

  async function cancel() {
    cancelledRef.current = true;
    abortRef.current?.abort();
    if (uploadingRef.current) await discardUpload(api, uploadingRef.current);
    setPhase("idle");
    setProgress(null);
  }

  const c = t.clean;
  const tr = t.trailer;
  const translateField = (
    <div className="flex max-w-sm flex-col gap-2">
      <Label htmlFor="subtitle-language">{u.subtitleLanguage}</Label>
      <select
        id="subtitle-language"
        value={optionsDraft.subtitle_language ?? ""}
        disabled={busy}
        onChange={(e) => setOptionsDraft((d) => ({ ...d, subtitle_language: e.target.value || null }))}
        className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
      >
        <option value="">{u.sameLanguage}</option>
        {SUBTITLE_LANGUAGES.map((l) => (
          <option key={l} value={l}>{u.translateTo(u.languages[l] ?? l)}</option>
        ))}
      </select>
      {optionsDraft.subtitle_language && <p className="text-xs text-muted-foreground">{u.translateHint}</p>}
    </div>
  );

  return (
    <div className="flex flex-col gap-6">
      {outOfMinutes && (
        <Alert variant="destructive">
          <AlertTitle>{u.outOfMinutesTitle}</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-2">
            {u.outOfMinutesText}
            <PlansLink />
          </AlertDescription>
        </Alert>
      )}

      <div
        role="button"
        tabIndex={0}
        aria-label={u.selectVideo}
        onClick={() => !busy && inputRef.current?.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && !busy && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-4 rounded-3xl border-2 border-dashed px-6 py-12 text-center transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
          dragging
            ? "border-primary bg-brand-soft"
            : "border-primary/40 bg-brand-soft/30 hover:border-primary hover:bg-brand-soft/70",
          busy && "pointer-events-none opacity-60",
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept.join(",") + (AUDIO_MODES.includes(mode) ? ",video/*,audio/*" : ",video/*")}
          className="hidden"
          onChange={(e) => pick(e.target.files?.[0])}
        />
        {file ? (
          <>
            <span className="flex size-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-sm">
              <FileVideoIcon className="size-7" />
            </span>
            <div>
              <p className="font-medium break-all">{file.name}</p>
              <p className="text-sm text-muted-foreground">
                {formatBytes(file.size)}
                {duration ? ` · ${formatDuration(duration, u.lessThanMinute)}` : ""}
              </p>
            </div>
            {!busy && (
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  setFile(null);
                  setFileUrl(null);
                  setTrim(null);
                  setDuration(null);
                  if (inputRef.current) inputRef.current.value = "";
                }}
              >
                <XIcon /> {u.changeVideo}
              </Button>
            )}
          </>
        ) : (
          <>
            <span className="flex size-14 items-center justify-center rounded-2xl bg-card text-brand-ink shadow-sm ring-1 ring-primary/30">
              <UploadCloudIcon className="size-7" />
            </span>
            <div>
              <p className="font-medium">{u.drop}</p>
              <p className="text-sm text-muted-foreground">
                {(AUDIO_MODES.includes(mode) ? u.dropHintAudio : u.dropHint)(formatBytes(maxBytes), me.plan.max_video_minutes)}
              </p>
            </div>
          </>
        )}
      </div>
      {fileError && <p className="-mt-3 text-sm text-destructive" role="alert">{fileError}</p>}

      {file && fileUrl && (
        <TrimSelector
          src={fileUrl}
          duration={duration}
          value={trim}
          onChange={setTrim}
          onDuration={(d, w, h) => {
            setDuration(d);
            if (!w || !h) return;
            setHighRes(Math.min(w, h) > 1080);
            const frame: ClipFormat = w / h < 0.8 ? "vertical" : w / h < 1.25 ? "square" : "horizontal";
            setSourceFrame(frame);
            // Al cambiar de formato, el destino por defecto es el contrario al del vídeo.
            if (reframeMode) {
              setOptionsDraft((o) => (o.format === frame
                ? { ...o, format: frame === "vertical" ? "horizontal" : "vertical" } : o));
            }
          }}
          maxSeconds={maxSeconds}
          minutesFactor={highRes ? 2 : 1}
          disabled={busy}
        />
      )}
      {tooBig && (
        <p className="-mt-3 text-sm text-destructive" role="alert">
          {partial
            ? u.tooBigPart(formatBytes(estimatedBytes), formatBytes(maxBytes))
            : u.tooBigWhole(formatBytes(file!.size), formatBytes(maxBytes))}{" "}
          <Link href="/plans" className="font-medium underline underline-offset-4">{t.plansPage.seePlans}</Link>
        </p>
      )}

      <div className="grid gap-6 sm:grid-cols-2">
        {!subtitleMode && (
          <div className="flex flex-col gap-2">
            <Label>{u.clipCount}</Label>
            <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label={u.clipCount}>
              {Array.from({ length: me.plan.max_clips_per_job }, (_, i) => i + 1).map((n) => (
                <Button
                  key={n}
                  type="button"
                  role="radio"
                  aria-checked={maxClips === n}
                  variant={maxClips === n ? "default" : "outline"}
                  size="sm"
                  className="min-w-9"
                  disabled={busy}
                  onClick={() => setMaxClips(n)}
                >
                  {n}
                </Button>
              ))}
            </div>
          </div>
        )}
        <div className="flex flex-col gap-2">
          <Label htmlFor="language">{u.videoLanguage}</Label>
          <select
            id="language"
            value={language}
            disabled={busy}
            onChange={(e) => setLanguage(e.target.value)}
            className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
          >
            {LANGUAGES.map((l) => (
              <option key={l} value={l}>
                {u.languages[l]}
              </option>
            ))}
          </select>
        </div>
      </div>

      {cleanMode && (
        <div className="flex flex-col gap-5 rounded-2xl border bg-muted/30 p-4 sm:p-5">
          <div className="flex flex-col gap-2">
            <Label>{c.pace}</Label>
            <div className="flex flex-wrap items-center gap-3">
              <Segmented
                label={c.pace}
                value={optionsDraft.clean_pace}
                disabled={busy}
                onChange={(clean_pace) => setOptionsDraft((d) => ({ ...d, clean_pace }))}
                options={(["natural", "normal", "fast"] as const).map((v) => ({ value: v, label: c.paces[v][0] }))}
              />
              <span className="text-xs text-muted-foreground">{c.paces[optionsDraft.clean_pace][1]}</span>
            </div>
          </div>
          <div className="flex items-center justify-between gap-4">
            <div>
              <Label htmlFor="clean-fillers">{c.fillersLabel}</Label>
              <p className="text-xs text-muted-foreground">{c.fillersHint}</p>
            </div>
            <Switch id="clean-fillers" checked={optionsDraft.clean_fillers} disabled={busy}
                    onCheckedChange={(v: boolean) => setOptionsDraft((d) => ({ ...d, clean_fillers: v }))} />
          </div>
        </div>
      )}

      {trailerMode && (
        <div className="flex flex-col gap-5 rounded-2xl border bg-muted/30 p-4 sm:p-5">
          <div className="flex flex-col gap-2">
            <Label>{tr.length}</Label>
            <div className="flex flex-wrap items-center gap-3">
              <Segmented
                label={tr.length}
                value={String(optionsDraft.trailer_seconds) as "30" | "60" | "90"}
                disabled={busy}
                onChange={(v) => setOptionsDraft((d) => ({ ...d, trailer_seconds: Number(v) as 30 | 60 | 90 }))}
                options={(["30", "60", "90"] as const).map((v) => ({ value: v, label: tr.lengths[v][0] }))}
              />
              <span className="text-xs text-muted-foreground">
                {tr.lengths[String(optionsDraft.trailer_seconds) as "30" | "60" | "90"][1]} · {tr.lengthHint}
              </span>
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="trailer-topic">
              {tr.topic} <span className="font-normal text-muted-foreground">{t.common.optional}</span>
            </Label>
            <Input id="trailer-topic" maxLength={200} value={optionsDraft.topic} disabled={busy}
                   placeholder={tr.topicPlaceholder}
                   onChange={(e) => setOptionsDraft((d) => ({ ...d, topic: e.target.value }))} />
            <p className="text-xs text-muted-foreground">{tr.topicHint}</p>
          </div>
        </div>
      )}

      {audiogramMode && (
        <AudiogramOptions
          look={optionsDraft}
          onChange={(look) => setOptionsDraft((o) => ({ ...o, ...look }))}
          image={audiogramImage}
          onImage={setAudiogramImage}
          logoUrl={optionsDraft.branding && prefs?.branding.has_logo ? prefs.logo_url : null}
          format={(optionsDraft.format === "original" ? "vertical" : optionsDraft.format) as ClipFormat}
          disabled={busy}
        />
      )}

      {textMode && (
        <div className="grid gap-5 rounded-2xl border bg-muted/30 p-4 sm:grid-cols-2 sm:p-5">
          <div className="flex flex-col gap-2">
            <Label htmlFor="text-language">{t.text.language}</Label>
            <select
              id="text-language"
              value={optionsDraft.subtitle_language ?? ""}
              disabled={busy}
              onChange={(e) => setOptionsDraft((d) => ({ ...d, subtitle_language: e.target.value || null }))}
              className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
            >
              <option value="">{t.text.sameLanguage}</option>
              {SUBTITLE_LANGUAGES.map((l) => (
                <option key={l} value={l}>{u.languages[l] ?? l}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium">{t.text.youGet}</span>
            <ul className="flex flex-col gap-1 text-sm">
              {t.text.items.map((item) => (
                <li key={item} className="flex items-start gap-2">
                  <CheckIcon className="mt-0.5 size-4 shrink-0 text-brand-ink" /> {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {options && !textMode && (
        <ProjectOptions
          value={options}
          onChange={setOptionsDraft}
          disabled={busy}
          sourceFrame={sourceFrame}
          subtitlesExtra={subtitleMode ? translateField : undefined}
          sameFormat={reframeMode && duration ? sourceFrame : null}
          fitPicker={reframeMode && (
            <ReframeFitPicker value={optionsDraft.reframe_fit} disabled={busy} src={fileUrl}
                              format={(options.format === "original" ? sourceFrame : options.format) as ClipFormat}
                              onChange={(reframe_fit) => setOptionsDraft((o) => ({ ...o, reframe_fit }))} />
          )}
          background={
            fileUrl ? (
              // Un fotograma del propio vídeo (del inicio del tramo) de fondo en la vista previa.
              <video
                key={`${fileUrl}-${Math.round(trim?.start ?? 0)}`}
                src={`${fileUrl}#t=${Math.max(0.5, trim?.start ?? 0.5)}`}
                muted
                playsInline
                preload="metadata"
                className="absolute inset-0 size-full object-cover"
              />
            ) : undefined
          }
        />
      )}

      {file && !busy && estimatedBytes >= LARGE_FILE && !tooBig && (
        <Alert>
          <AlertTitle>{u.largeTitle(formatBytes(estimatedBytes))}</AlertTitle>
          <AlertDescription>
            {u.largeText}
          </AlertDescription>
        </Alert>
      )}

      {busy ? (
        <div className="flex flex-col gap-2" aria-live="polite">
          <div className="flex justify-between gap-3 text-sm">
            <span>{u.phases[phase]}</span>
            {phase === "uploading" && progress && (
              <span className="tabular-nums text-muted-foreground">
                {Math.floor((progress.sentBytes / progress.totalBytes) * 100)}%
              </span>
            )}
            {phase === "trimming" && (
              <span className="tabular-nums text-muted-foreground">{Math.floor(trimProgress * 100)}%</span>
            )}
          </div>
          <Progress
            value={
              phase === "uploading" && progress
                ? (progress.sentBytes / progress.totalBytes) * 100
                : phase === "trimming"
                  ? trimProgress * 100
                  : 100
            }
            aria-label={u.progressLabel}
          />
          {phase === "uploading" && progress && (
            <p className="text-xs text-muted-foreground tabular-nums">
              {progress.resumed && u.resumed}
              {formatBytes(progress.sentBytes)} {u.of} {formatBytes(progress.totalBytes)}
              {progress.bytesPerSecond ? ` · ${formatSpeed(progress.bytesPerSecond)}` : ""}
              {progress.secondsLeft != null ? u.left(formatDuration(progress.secondsLeft, u.lessThanMinute)) : u.calculating}
            </p>
          )}
          {phase === "uploading" && (
            <Button variant="ghost" size="sm" className="self-start" onClick={cancel}>
              {u.cancel}
            </Button>
          )}
        </div>
      ) : (
        <Button size="lg" className="h-12 rounded-full text-base"
                disabled={!file || !duration || outOfMinutes || tooLong || tooBig} onClick={submit}>
          {cleanMode ? c.create : reframeMode ? t.reframe.create : trailerMode ? tr.create
            : audiogramMode ? t.audiogram.create : textMode ? t.text.create : subtitleMode ? u.createSubtitle : u.create}
        </Button>
      )}
      <p className="text-xs text-muted-foreground">
        {u.rightsStart}{" "}
        <Link href="/legal/terminos" className="underline underline-offset-4" target="_blank">
          {u.rightsTerms}
        </Link>
        ).{" "}
        {textMode ? u.purgeNote : u.keepNote(me.plan.retention_days)}
      </p>
    </div>
  );
}
