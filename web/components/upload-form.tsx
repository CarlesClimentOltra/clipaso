"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FileVideoIcon, UploadCloudIcon, XIcon } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { toast } from "sonner";

import { ProjectOptions, type ProjectOptionsValue } from "@/components/project-options";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { ApiError, type Me } from "@/lib/api/client";
import { useApi, useClipOptions, useCreateProject, usePreferences } from "@/lib/api/hooks";
import { discardUpload, type UploadProgress } from "@/lib/api/multipart-upload";
import { cn } from "@/lib/utils";

const ACCEPT = [".mp4", ".mov", ".mkv", ".webm", ".m4v"];
const LANGUAGES = [
  { value: "es", label: "Español" },
  { value: "en", label: "Inglés" },
  { value: "pt", label: "Portugués" },
  { value: "fr", label: "Francés" },
  { value: "it", label: "Italiano" },
  { value: "de", label: "Alemán" },
  { value: "auto", label: "Detectar automáticamente" },
];

type Phase = "idle" | "uploading" | "checking" | "starting";
const PHASE_LABEL: Record<Phase, string> = {
  idle: "",
  uploading: "Subiendo vídeo…",
  checking: "Comprobando el vídeo…",
  starting: "Iniciando el procesamiento…",
};

const LARGE_FILE = 1024 ** 3; // a partir de 1 GB avisamos de que la subida puede tardar

function formatBytes(bytes: number): string {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
  return `${Math.max(1, Math.round(bytes / 1024 ** 2))} MB`;
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return "menos de 1 min";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
}

function formatSpeed(bytesPerSecond: number): string {
  const mbps = (bytesPerSecond * 8) / 1e6;
  return `${mbps >= 10 ? Math.round(mbps) : mbps.toFixed(1)} Mbit/s`;
}

export function UploadForm({ me }: { me: Me }) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [maxClips, setMaxClips] = useState(Math.min(3, me.plan.max_clips_per_job));
  const [language, setLanguage] = useState("es");
  const [phase, setPhase] = useState<Phase>("idle");
  const [optionsDraft, setOptionsDraft] = useState<Omit<ProjectOptionsValue, "caption_style"> & {
    caption_style: ProjectOptionsValue["caption_style"] | null;
  }>({ format: "vertical", duration: "auto", topic: "", keep_source: true, branding: true, caption_style: null });
  const { data: prefs } = usePreferences();
  const { data: catalog } = useClipOptions();
  // Hasta que el usuario toque el estilo, se usa el suyo por defecto (o el primero del catálogo).
  const defaultStyle = prefs?.caption_style ?? catalog?.presets[0]?.style ?? null;
  const options: ProjectOptionsValue | null =
    optionsDraft.caption_style ?? defaultStyle
      ? { ...optionsDraft, caption_style: (optionsDraft.caption_style ?? defaultStyle)! }
      : null;
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const cancelledRef = useRef(false);
  const create = useCreateProject();
  const api = useApi();

  const busy = phase !== "idle";
  const outOfMinutes = me.usage.remaining_minutes <= 0;
  const maxBytes = me.plan.max_upload_mb * 1024 * 1024;

  function pick(candidate: File | undefined) {
    setFileError(null);
    if (!candidate) return;
    const ext = candidate.name.slice(candidate.name.lastIndexOf(".")).toLowerCase();
    if (!ACCEPT.includes(ext)) {
      setFileError("Formato no compatible. Sube un vídeo MP4, MOV, MKV o WEBM.");
      return;
    }
    if (candidate.size > maxBytes) {
      setFileError(`El archivo pesa ${formatBytes(candidate.size)} y tu plan permite hasta ${formatBytes(maxBytes)}.`);
      return;
    }
    setFile(candidate);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (!busy) pick(e.dataTransfer.files?.[0]);
  }

  async function submit() {
    if (!file) return;
    abortRef.current = new AbortController();
    cancelledRef.current = false;
    setProgress(null);
    try {
      const job = await create.mutateAsync({
        file,
        maxClips,
        language,
        options: options ?? { ...optionsDraft, caption_style: null },
        onUploadProgress: setProgress,
        onPhase: setPhase,
        signal: abortRef.current.signal,
      });
      toast.success("¡Vídeo recibido! Estamos preparando tus clips.");
      router.push(`/projects/${job.id}`);
    } catch (err) {
      setPhase("idle");
      if (cancelledRef.current) return;
      const interrupted = err instanceof ApiError && ["network_error", "part_failed"].includes(err.code);
      toast.error(
        interrupted
          ? "La subida se interrumpió. Pulsa «Crear clips» de nuevo y continuará donde se quedó."
          : err instanceof ApiError
            ? err.message
            : "Algo salió mal. Inténtalo de nuevo.",
      );
    }
  }

  async function cancel() {
    cancelledRef.current = true;
    abortRef.current?.abort();
    if (file) await discardUpload(api, file);
    setPhase("idle");
    setProgress(null);
  }

  return (
    <div className="flex flex-col gap-6">
      {outOfMinutes && (
        <Alert variant="destructive">
          <AlertTitle>Has agotado los minutos de este mes</AlertTitle>
          <AlertDescription>Tu plan se renueva a principios de mes. Pronto podrás ampliar tu plan desde aquí.</AlertDescription>
        </Alert>
      )}

      <div
        role="button"
        tabIndex={0}
        aria-label="Seleccionar vídeo"
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
          accept={ACCEPT.join(",") + ",video/*"}
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
              <p className="text-sm text-muted-foreground">{formatBytes(file.size)}</p>
            </div>
            {!busy && (
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  setFile(null);
                  if (inputRef.current) inputRef.current.value = "";
                }}
              >
                <XIcon /> Cambiar vídeo
              </Button>
            )}
          </>
        ) : (
          <>
            <span className="flex size-14 items-center justify-center rounded-2xl bg-card text-brand-ink shadow-sm ring-1 ring-primary/30">
              <UploadCloudIcon className="size-7" />
            </span>
            <div>
              <p className="font-medium">Arrastra tu vídeo aquí o haz clic para elegirlo</p>
              <p className="text-sm text-muted-foreground">
                MP4, MOV, MKV o WEBM · hasta {formatBytes(maxBytes)} y {me.plan.max_video_minutes} min de duración
              </p>
            </div>
          </>
        )}
      </div>
      {fileError && <p className="-mt-3 text-sm text-destructive" role="alert">{fileError}</p>}

      <div className="grid gap-6 sm:grid-cols-2">
        <div className="flex flex-col gap-2">
          <Label>Número de clips</Label>
          <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Número de clips">
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
        <div className="flex flex-col gap-2">
          <Label htmlFor="language">Idioma del vídeo</Label>
          <select
            id="language"
            value={language}
            disabled={busy}
            onChange={(e) => setLanguage(e.target.value)}
            className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
          >
            {LANGUAGES.map((l) => (
              <option key={l.value} value={l.value}>
                {l.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {options && <ProjectOptions me={me} value={options} onChange={setOptionsDraft} disabled={busy} />}

      {file && !busy && file.size >= LARGE_FILE && (
        <Alert>
          <AlertTitle>Archivo grande ({formatBytes(file.size)})</AlertTitle>
          <AlertDescription>
            La subida puede tardar varios minutos según tu conexión. Si se corta, podrás continuar donde se quedó.
            Consejo: exportar el vídeo en 1080p lo hace mucho más rápido sin perder calidad en los clips.
          </AlertDescription>
        </Alert>
      )}

      {busy ? (
        <div className="flex flex-col gap-2" aria-live="polite">
          <div className="flex justify-between gap-3 text-sm">
            <span>{PHASE_LABEL[phase]}</span>
            {phase === "uploading" && progress && (
              <span className="tabular-nums text-muted-foreground">
                {Math.floor((progress.sentBytes / progress.totalBytes) * 100)}%
              </span>
            )}
          </div>
          <Progress
            value={phase === "uploading" && progress ? (progress.sentBytes / progress.totalBytes) * 100 : 100}
            aria-label="Progreso de la subida"
          />
          {phase === "uploading" && progress && (
            <p className="text-xs text-muted-foreground tabular-nums">
              {progress.resumed && "Continuando una subida anterior · "}
              {formatBytes(progress.sentBytes)} de {formatBytes(progress.totalBytes)}
              {progress.bytesPerSecond ? ` · ${formatSpeed(progress.bytesPerSecond)}` : ""}
              {progress.secondsLeft != null ? ` · quedan ${formatDuration(progress.secondsLeft)}` : " · calculando tiempo…"}
            </p>
          )}
          {phase === "uploading" && (
            <Button variant="ghost" size="sm" className="self-start" onClick={cancel}>
              Cancelar subida
            </Button>
          )}
        </div>
      ) : (
        <Button size="lg" className="h-12 rounded-full text-base" disabled={!file || outOfMinutes} onClick={submit}>
          Crear clips
        </Button>
      )}
      <p className="text-xs text-muted-foreground">
        Al subir un vídeo confirmas que tienes los derechos necesarios sobre su contenido y el permiso de las personas
        que aparecen en él (ver{" "}
        <Link href="/legal/terminos" className="underline underline-offset-4" target="_blank">
          Términos
        </Link>
        ).{" "}
        {optionsDraft.keep_source
          ? `El vídeo original se guarda ${me.plan.retention_days} días para que puedas editar los clips y después se borra.`
          : "El vídeo original se borra al terminar de procesarlo."}
      </p>
    </div>
  );
}
