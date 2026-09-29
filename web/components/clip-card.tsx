"use client";

import Link from "next/link";
import {
  CheckIcon,
  CopyIcon,
  ImageIcon,
  Loader2Icon,
  PencilIcon,
  ScissorsIcon,
  ThumbsDownIcon,
  ThumbsUpIcon,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { ClipDownloads } from "@/components/clip-downloads";
import { CoverEditor } from "@/components/editor/cover-editor";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, type Clip, type Job } from "@/lib/api/client";
import { useRateClip, useUpdateClip } from "@/lib/api/hooks";
import { useI18n } from "@/lib/i18n";
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
  const { t } = useI18n();
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
      {copied ? t.common.copied : label}
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
  const { t } = useI18n();
  const c = t.clip;
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
      toast.success(c.saved);
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : c.saveError);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{c.textsTitle}</DialogTitle>
          <DialogDescription>{c.textsLead}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor={`title-${clip.id}`}>{c.title}</Label>
            <Input id={`title-${clip.id}`} maxLength={255} value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor={`desc-${clip.id}`}>{c.description}</Label>
            <Textarea id={`desc-${clip.id}`} rows={3} maxLength={2000} value={description}
                      onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor={`tags-${clip.id}`}>{c.hashtags}</Label>
            <Input id={`tags-${clip.id}`} value={hashtags} placeholder="#viral #podcast"
                   onChange={(e) => setHashtags(e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <DialogClose render={<Button variant="outline" />}>{t.common.cancel}</DialogClose>
          <Button onClick={save} disabled={update.isPending}>
            {update.isPending ? t.common.saving : t.common.save}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ClipCard({ clip, job }: { clip: Clip; job: Job }) {
  const rate = useRateClip(job.id);
  const { t } = useI18n();
  const c = t.clip;
  const [editing, setEditing] = useState(false);
  const [coverOpen, setCoverOpen] = useState(false);
  const rendering = clip.status === "rendering";
  const base = `${slug(job.title)}-${String(clip.rank).padStart(2, "0")}-${slug(clip.title)}`;
  const publishText = [clip.description, hashtagLine(clip)].filter(Boolean).join("\n\n");

  function vote(value: 1 | -1) {
    rate.mutate({ clipId: clip.id, value: clip.rating === value ? 0 : value });
  }

  return (
    <Card className="overflow-hidden pt-0">
      <div className="relative">
        <ClipPlayer
          key={clip.version}
          src={clip.video_url}
          // La portada (si encaja con el formato del clip) es lo primero que se ve, como en TikTok o YouTube.
          poster={
            (job.frame === "vertical" ? clip.cover?.vertical_url
              : job.frame === "horizontal" ? clip.cover?.horizontal_url : null)
            ?? clip.thumbnail_url ?? undefined
          }
          title={clip.title}
          rank={clip.rank}
          aspect={CLIP_ASPECT[job.frame]}
        />
        {rendering && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/60 text-sm text-white">
            <Loader2Icon className="size-6 animate-spin" />
            {c.rendering}
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
            <AlertDescription>{clip.render_error} {c.keptPrevious}</AlertDescription>
          </Alert>
        )}
        {(clip.description || clip.hashtags.length > 0) && (
          <div className="flex flex-col gap-1 rounded-lg bg-muted/50 p-3">
            {clip.description && <p className="line-clamp-4 whitespace-pre-line">{clip.description}</p>}
            {clip.hashtags.length > 0 && <p className="text-brand-ink">{hashtagLine(clip)}</p>}
            <div className="-mx-2 -mb-1 flex flex-wrap gap-0.5">
              <CopyButton text={clip.title} label={c.titleCopy} />
              {publishText && <CopyButton text={publishText} label={c.descriptionCopy} />}
              <Button type="button" variant="ghost" size="sm" onClick={() => setEditing(true)}>
                <PencilIcon /> {t.common.edit}
              </Button>
            </div>
          </div>
        )}
        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <span>
            {c.range(Math.round(clip.duration), formatTimestamp(clip.start), formatTimestamp(clip.end))}
          </span>
          <span className="flex items-center gap-0.5" aria-label={c.rate}>
            {clip.cover && (
              <Button variant="ghost" size="sm" onClick={() => setCoverOpen(true)} className="mr-1 h-7 px-2 text-xs">
                <ImageIcon /> {t.cover.button}
              </Button>
            )}
            <Button variant="ghost" size="icon-sm" aria-pressed={clip.rating === 1} aria-label={c.like}
                    onClick={() => vote(1)} className={cn(clip.rating === 1 && "text-brand-ink")}>
              <ThumbsUpIcon className={cn(clip.rating === 1 && "fill-current")} />
            </Button>
            <Button variant="ghost" size="icon-sm" aria-pressed={clip.rating === -1} aria-label={c.dislike}
                    onClick={() => vote(-1)} className={cn(clip.rating === -1 && "text-destructive")}>
              <ThumbsDownIcon className={cn(clip.rating === -1 && "fill-current")} />
            </Button>
          </span>
        </div>
      </CardContent>
      <CardFooter className="mt-auto flex gap-2">
        <ClipDownloads key={clip.version} clipId={clip.id} downloadUrl={clip.download_url} filenameBase={base}
                       cover={clip.cover}
                       className="flex-1" />
        {job.can_edit ? (
          <Link
            href={`/projects/${job.id}/clips/${clip.id}`}
            className={buttonVariants({ className: cn("flex-1", rendering && "pointer-events-none opacity-50") })}
            aria-disabled={rendering}
          >
            <ScissorsIcon /> {c.editClip}
          </Link>
        ) : (
          <Button variant="secondary" className="flex-1" onClick={() => setEditing(true)}>
            <PencilIcon /> {c.texts}
          </Button>
        )}
      </CardFooter>
      {editing && <EditTextsDialog clip={clip} jobId={job.id} open={editing} onOpenChange={setEditing} />}
      {coverOpen && clip.cover && (
        <Dialog open={coverOpen} onOpenChange={setCoverOpen}>
          <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-3xl">
            <DialogHeader>
              <DialogTitle>{t.cover.title}</DialogTitle>
              <DialogDescription>{clip.title}</DialogDescription>
            </DialogHeader>
            <CoverEditor clip={clip} jobId={job.id} previewUrl={null} canChangeFrame={false}
                         frameMessage={job.can_edit ? t.cover.frameInEditor : t.cover.noSource} />
          </DialogContent>
        </Dialog>
      )}
    </Card>
  );
}
