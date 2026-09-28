"use client";

import Link from "next/link";
import {
  CaptionsIcon,
  CheckIcon,
  ChevronDownIcon,
  CopyIcon,
  DownloadIcon,
  Loader2Icon,
  PencilIcon,
  ScissorsIcon,
  ThumbsDownIcon,
  ThumbsUpIcon,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { CLIP_ASPECT, ClipPlayer } from "@/components/clip-player";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, type Clip, type Job } from "@/lib/api/client";
import { useDownloadCaptions, useRateClip, useUpdateClip } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";

export function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function slug(text: string): string {
  return (
    text
      .normalize("NFKD")
      .replace(/[̀-ͯ]/g, "")
      .replace(/[^A-Za-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
      .toLowerCase()
      .slice(0, 50) || "clip"
  );
}

function hashtagLine(clip: Clip) {
  return clip.hashtags.map((t) => `#${t}`).join(" ");
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? <CheckIcon /> : <CopyIcon />}
      {copied ? "Copiado" : label}
    </Button>
  );
}

function EditTextsDialog({ clip, jobId, open, onOpenChange }: {
  clip: Clip;
  jobId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const update = useUpdateClip(jobId);
  const [title, setTitle] = useState(clip.title);
  const [description, setDescription] = useState(clip.description);
  const [hashtags, setHashtags] = useState(hashtagLine(clip));

  async function save() {
    try {
      await update.mutateAsync({
        clipId: clip.id,
        title,
        description,
        hashtags: hashtags.split(/[\s,]+/).filter(Boolean),
      });
      toast.success("Textos guardados");
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudieron guardar los textos.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Textos para publicar</DialogTitle>
          <DialogDescription>Lo que pegarás al subir el clip a TikTok, Reels o Shorts.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor={`title-${clip.id}`}>Título</Label>
            <Input id={`title-${clip.id}`} maxLength={255} value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor={`desc-${clip.id}`}>Descripción</Label>
            <Textarea id={`desc-${clip.id}`} rows={3} maxLength={2000} value={description}
                      onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor={`tags-${clip.id}`}>Hashtags</Label>
            <Input id={`tags-${clip.id}`} value={hashtags} placeholder="#viral #podcast"
                   onChange={(e) => setHashtags(e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <DialogClose render={<Button variant="outline" />}>Cancelar</DialogClose>
          <Button onClick={save} disabled={update.isPending}>
            {update.isPending ? "Guardando…" : "Guardar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ClipCard({ clip, job }: { clip: Clip; job: Job }) {
  const rate = useRateClip(job.id);
  const captions = useDownloadCaptions();
  const [editing, setEditing] = useState(false);
  const rendering = clip.status === "rendering";
  const base = `${slug(job.title)}-${String(clip.rank).padStart(2, "0")}-${slug(clip.title)}`;
  const publishText = [clip.description, hashtagLine(clip)].filter(Boolean).join("\n\n");

  function vote(value: 1 | -1) {
    rate.mutate({ clipId: clip.id, value: clip.rating === value ? 0 : value });
  }

  async function downloadCaptions(format: "srt" | "vtt") {
    try {
      await captions.mutateAsync({ clipId: clip.id, format, filename: `${base}.${format}` });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudieron descargar los subtítulos.");
    }
  }

  return (
    <Card className="overflow-hidden pt-0">
      <div className="relative">
        <ClipPlayer
          key={clip.version}
          src={clip.video_url}
          poster={clip.thumbnail_url ?? undefined}
          title={clip.title}
          rank={clip.rank}
          aspect={CLIP_ASPECT[job.options.format ?? "vertical"]}
        />
        {rendering && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/60 text-sm text-white">
            <Loader2Icon className="size-6 animate-spin" />
            Generando la nueva versión…
          </div>
        )}
      </div>
      <CardHeader>
        <CardTitle className="line-clamp-2 leading-snug">{clip.title}</CardTitle>
        {clip.reason && <CardDescription className="line-clamp-3">{clip.reason}</CardDescription>}
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">
        {clip.status === "failed" && clip.render_error && (
          <Alert variant="destructive">
            <AlertDescription>{clip.render_error} Se mantiene la versión anterior.</AlertDescription>
          </Alert>
        )}
        {(clip.description || clip.hashtags.length > 0) && (
          <div className="flex flex-col gap-1 rounded-lg bg-muted/50 p-3">
            {clip.description && <p className="line-clamp-4 whitespace-pre-line">{clip.description}</p>}
            {clip.hashtags.length > 0 && <p className="text-brand-ink">{hashtagLine(clip)}</p>}
            <div className="-mx-2 -mb-1 flex flex-wrap gap-0.5">
              <CopyButton text={clip.title} label="Título" />
              {publishText && <CopyButton text={publishText} label="Descripción" />}
              <Button type="button" variant="ghost" size="sm" onClick={() => setEditing(true)}>
                <PencilIcon /> Editar
              </Button>
            </div>
          </div>
        )}
        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <span>
            {Math.round(clip.duration)} s · del {formatTimestamp(clip.start)} al {formatTimestamp(clip.end)}
          </span>
          <span className="flex gap-0.5" aria-label="Valorar el clip">
            <Button variant="ghost" size="icon-sm" aria-pressed={clip.rating === 1} aria-label="Me gusta"
                    onClick={() => vote(1)} className={cn(clip.rating === 1 && "text-brand-ink")}>
              <ThumbsUpIcon className={cn(clip.rating === 1 && "fill-current")} />
            </Button>
            <Button variant="ghost" size="icon-sm" aria-pressed={clip.rating === -1} aria-label="No me gusta"
                    onClick={() => vote(-1)} className={cn(clip.rating === -1 && "text-destructive")}>
              <ThumbsDownIcon className={cn(clip.rating === -1 && "fill-current")} />
            </Button>
          </span>
        </div>
      </CardContent>
      <CardFooter className="mt-auto flex gap-2">
        <div className="flex flex-1">
          <a href={clip.download_url} download
             className={buttonVariants({ variant: "outline", className: "flex-1 rounded-r-none" })}>
            <DownloadIcon /> MP4
          </a>
          <DropdownMenu>
            <DropdownMenuTrigger
              aria-label="Más descargas"
              className={buttonVariants({ variant: "outline", size: "icon", className: "rounded-l-none border-l-0" })}
            >
              <ChevronDownIcon />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => downloadCaptions("srt")}>
                <CaptionsIcon /> Subtítulos SRT
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => downloadCaptions("vtt")}>
                <CaptionsIcon /> Subtítulos VTT
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        {job.can_edit ? (
          <Link
            href={`/projects/${job.id}/clips/${clip.id}`}
            className={buttonVariants({ className: cn("flex-1", rendering && "pointer-events-none opacity-50") })}
            aria-disabled={rendering}
          >
            <ScissorsIcon /> Editar clip
          </Link>
        ) : (
          <Button variant="secondary" className="flex-1" onClick={() => setEditing(true)}>
            <PencilIcon /> Textos
          </Button>
        )}
      </CardFooter>
      {editing && <EditTextsDialog clip={clip} jobId={job.id} open={editing} onOpenChange={setEditing} />}
    </Card>
  );
}
