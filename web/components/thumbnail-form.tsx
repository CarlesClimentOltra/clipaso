"use client";

import { useRouter } from "next/navigation";
import { FileVideoIcon, ImageIcon, SparklesIcon, UploadCloudIcon, XIcon } from "lucide-react";
import { useEffect, useRef, useState, type DragEvent } from "react";
import { toast } from "sonner";
import { track } from "@vercel/analytics";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Switch } from "@/components/ui/switch";
import { ApiError } from "@/lib/api/client";
import { useCreateThumbnail, usePreferences } from "@/lib/api/hooks";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { extractFrames } from "@/lib/video-frames";

const FRAMES = 20;

/** Modo «Generar miniatura»: el vídeo se queda en el ordenador del usuario; solo viajan unos fotogramas. */
export function ThumbnailForm() {
  const router = useRouter();
  const { t, locale } = useI18n();
  const m = t.thumbnail;
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fileUrl, setFileUrl] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [topic, setTopic] = useState("");
  const [branding, setBranding] = useState(true);
  const [step, setStep] = useState<"idle" | "reading" | "thinking">("idle");
  const [read, setRead] = useState(0);
  const create = useCreateThumbnail();
  const { data: prefs } = usePreferences();
  const hasBrand = !!prefs && (!!prefs.branding.handle || prefs.branding.has_logo);
  const busy = step !== "idle";

  useEffect(() => () => {
    if (fileUrl) URL.revokeObjectURL(fileUrl);
  }, [fileUrl]);

  function pick(candidate: File | undefined) {
    if (!candidate) return;
    if (!candidate.type.startsWith("video/") && !/\.(mp4|mov|mkv|webm|m4v)$/i.test(candidate.name)) {
      toast.error(t.upload.formatError);
      return;
    }
    setFile(candidate);
    setFileUrl(URL.createObjectURL(candidate));
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (!busy) pick(e.dataTransfer.files?.[0]);
  }

  async function generate() {
    if (!file) return;
    try {
      setStep("reading");
      setRead(0);
      const frames = await extractFrames(file, FRAMES, 1280, (done) => setRead(done));
      setStep("thinking");
      const job = await create.mutateAsync({
        filename: file.name, topic: topic.trim(), language: locale, branding: branding && hasBrand, frames,
      });
      track("project_created", { mode: "thumbnail" });
      toast.success(m.done);
      router.push(`/projects/${job.id}`);
    } catch (err) {
      setStep("idle");
      toast.error(err instanceof ApiError ? err.message : m.readError);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div
        role="button"
        tabIndex={0}
        aria-label={t.upload.selectVideo}
        onClick={() => !busy && inputRef.current?.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && !busy && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-4 rounded-3xl border-2 border-dashed px-6 py-10 text-center transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
          dragging ? "border-primary bg-brand-soft" : "border-primary/40 bg-brand-soft/30 hover:border-primary hover:bg-brand-soft/70",
          busy && "pointer-events-none opacity-60",
        )}
      >
        <input ref={inputRef} type="file" accept="video/*,.mp4,.mov,.mkv,.webm,.m4v" className="hidden"
               onChange={(e) => pick(e.target.files?.[0])} />
        {file && fileUrl ? (
          <>
            <video src={`${fileUrl}#t=1`} muted playsInline preload="metadata"
                   className="max-h-48 rounded-xl bg-black shadow-sm" />
            <div>
              <p className="flex items-center justify-center gap-2 font-medium break-all">
                <FileVideoIcon className="size-4 shrink-0 text-brand-ink" /> {file.name}
              </p>
              <p className="text-sm text-muted-foreground">{m.staysHere}</p>
            </div>
            {!busy && (
              <Button variant="ghost" size="sm" onClick={(e) => {
                e.stopPropagation();
                setFile(null);
                setFileUrl(null);
                if (inputRef.current) inputRef.current.value = "";
              }}>
                <XIcon /> {t.upload.changeVideo}
              </Button>
            )}
          </>
        ) : (
          <>
            <span className="flex size-14 items-center justify-center rounded-2xl bg-card text-brand-ink shadow-sm ring-1 ring-primary/30">
              <UploadCloudIcon className="size-7" />
            </span>
            <div>
              <p className="font-medium">{t.upload.drop}</p>
              <p className="text-sm text-muted-foreground">{m.dropHint}</p>
            </div>
          </>
        )}
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor="thumb-topic">
          {m.topic} <span className="font-normal text-muted-foreground">{t.common.optional}</span>
        </Label>
        <Input id="thumb-topic" maxLength={300} value={topic} disabled={busy} placeholder={m.topicPlaceholder}
               onChange={(e) => setTopic(e.target.value)} />
        <p className="text-xs text-muted-foreground">{m.topicHint}</p>
      </div>

      {hasBrand && (
        <div className="flex items-center justify-between gap-4 rounded-xl border p-4">
          <div>
            <Label htmlFor="thumb-brand">{m.brand}</Label>
            <p className="text-xs text-muted-foreground">{m.brandHint}</p>
          </div>
          <Switch id="thumb-brand" checked={branding} disabled={busy} onCheckedChange={(c: boolean) => setBranding(c)} />
        </div>
      )}

      {busy ? (
        <div className="flex flex-col gap-2" aria-live="polite">
          <div className="flex justify-between gap-3 text-sm">
            <span className="flex items-center gap-2">
              {step === "reading" ? <ImageIcon className="size-4" /> : <SparklesIcon className="size-4 animate-pulse" />}
              {step === "reading" ? m.reading(read, FRAMES) : m.thinking}
            </span>
          </div>
          <Progress value={step === "reading" ? (read / FRAMES) * 80 : 92} aria-label={m.progress} />
        </div>
      ) : (
        <Button size="lg" className="h-12 rounded-full text-base" disabled={!file} onClick={generate}>
          <SparklesIcon /> {m.create}
        </Button>
      )}
      <p className="text-xs text-muted-foreground">{m.note}</p>
    </div>
  );
}
