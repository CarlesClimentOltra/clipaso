"use client";

import { useRouter } from "next/navigation";
import { FileVideoIcon, UploadCloudIcon, XIcon } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { ApiError, type Me } from "@/lib/api/client";
import { useCreateProject } from "@/lib/api/hooks";
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

function formatBytes(bytes: number): string {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
  return `${Math.max(1, Math.round(bytes / 1024 ** 2))} MB`;
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
  const [uploadPct, setUploadPct] = useState(0);
  const create = useCreateProject();

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
    setUploadPct(0);
    try {
      const job = await create.mutateAsync({
        file,
        maxClips,
        language,
        onUploadProgress: setUploadPct,
        onPhase: setPhase,
        signal: abortRef.current.signal,
      });
      toast.success("¡Vídeo recibido! Estamos preparando tus clips.");
      router.push(`/projects/${job.id}`);
    } catch (err) {
      setPhase("idle");
      if (err instanceof ApiError && err.code === "aborted") return;
      toast.error(err instanceof ApiError ? err.message : "Algo salió mal. Inténtalo de nuevo.");
    }
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
          "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-10 text-center transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
          dragging ? "border-primary bg-primary/5" : "border-border hover:border-primary/50 hover:bg-muted/40",
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
            <FileVideoIcon className="size-10 text-primary" />
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
            <UploadCloudIcon className="size-10 text-muted-foreground" />
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

      {busy ? (
        <div className="flex flex-col gap-2" aria-live="polite">
          <div className="flex justify-between text-sm">
            <span>{PHASE_LABEL[phase]}</span>
            {phase === "uploading" && <span className="tabular-nums text-muted-foreground">{Math.round(uploadPct * 100)}%</span>}
          </div>
          <Progress value={phase === "uploading" ? uploadPct * 100 : 100} aria-label="Progreso de la subida" />
          {phase === "uploading" && (
            <Button variant="ghost" size="sm" className="self-start" onClick={() => abortRef.current?.abort()}>
              Cancelar subida
            </Button>
          )}
        </div>
      ) : (
        <Button size="lg" className="h-10" disabled={!file || outOfMinutes} onClick={submit}>
          Crear clips
        </Button>
      )}
      <p className="text-xs text-muted-foreground">
        Al subir un vídeo confirmas que tienes los derechos necesarios sobre su contenido.
      </p>
    </div>
  );
}
