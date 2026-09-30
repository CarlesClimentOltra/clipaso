"use client";

import {
  CaptionsIcon,
  CheckIcon,
  ChevronDownIcon,
  ImageIcon,
  DownloadIcon,
  FilmIcon,
  Loader2Icon,
  LockIcon,
  MusicIcon,
  RotateCcwIcon,
  SparklesIcon,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { buttonVariants } from "@/components/ui/button";
import { PlansLink, toastError } from "@/components/error-toast";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ApiError, type ClipCover, type ClipExport } from "@/lib/api/client";
import { downloadUrl, useClipExports, useDownloadCaptions, useRequestExport } from "@/lib/api/hooks";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

function formatSize(bytes?: number | null) {
  if (!bytes) return "";
  return bytes >= 1024 ** 3 ? `${(bytes / 1024 ** 3).toFixed(1)} GB` : `${Math.max(1, Math.round(bytes / 1024 ** 2))} MB`;
}

/** Botón de descarga del clip: MP4 en 1080p directo y, en el menú, otras calidades, MP3 y subtítulos. */
export function ClipDownloads({
  clipId,
  downloadUrl: mainUrl,
  filenameBase,
  cover,
  className,
}: {
  clipId: string;
  downloadUrl: string;
  filenameBase: string;
  cover?: ClipCover | null;
  className?: string;
}) {
  const { t } = useI18n();
  const d = t.downloads;
  const [open, setOpen] = useState(false);
  const [watching, setWatching] = useState(false);
  const exportsQuery = useClipExports(clipId, open || watching);
  const request = useRequestExport(clipId);
  const captions = useDownloadCaptions();
  const items = exportsQuery.data?.items ?? [];
  const pending = items.some((i) => i.status === "pending");

  // Aviso cuando termina de generarse una calidad pedida (aunque el menú esté cerrado).
  const previous = useRef<Record<string, string>>({});
  useEffect(() => {
    for (const item of items) {
      const id = `${item.format}-${item.quality}`;
      if (previous.current[id] === "pending" && item.status === "ready" && item.url) {
        const url = item.url;
        toast.success(d.ready(label(item)), { action: { label: d.download, onClick: () => downloadUrl(url) } });
      }
      if (previous.current[id] === "pending" && item.status === "failed") toast.error(item.error_message ?? d.failed);
      previous.current[id] = item.status;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [exportsQuery.data]);

  if (watching && !pending && exportsQuery.data && !open) {
    // nada pendiente: deja de consultar
    setWatching(false);
  }

  function label(item: ClipExport) {
    if (item.format === "mp3") return d.mp3;
    return item.quality === "2160p" ? "4K" : item.quality ?? "";
  }

  async function pick(item: ClipExport) {
    if (item.status === "ready" && item.url) {
      downloadUrl(item.url);
      return;
    }
    if (item.status === "pending") return;
    if (item.status === "locked") {
      toast.info(d.lockedHint(label(item)), { action: <PlansLink className="ml-auto" /> });
      return;
    }
    try {
      const data = await request.mutateAsync({ format: item.format, quality: item.quality });
      const now = data.items.find((i) => i.format === item.format && i.quality === item.quality);
      if (now?.status === "ready" && now.url) downloadUrl(now.url);
      else {
        setWatching(true);
        toast.info(d.preparing(label(item)));
      }
    } catch (err) {
      toastError(err, d.failed);
    }
  }

  async function downloadCaptions(format: "srt" | "vtt") {
    try {
      await captions.mutateAsync({ clipId, format, filename: `${filenameBase}.${format}` });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : t.clip.captionsError);
    }
  }

  function status(item: ClipExport) {
    if (item.status === "ready") {
      return <span className="ml-auto text-xs text-muted-foreground tabular-nums">{formatSize(item.size_bytes)}</span>;
    }
    if (item.status === "pending") {
      return <span className="ml-auto flex items-center gap-1 text-xs text-muted-foreground">
        <Loader2Icon className="size-3 animate-spin" /> {d.pending}
      </span>;
    }
    if (item.status === "failed") {
      return <span className="ml-auto flex items-center gap-1 text-xs text-destructive"><RotateCcwIcon className="size-3" /> {d.retry}</span>;
    }
    if (item.status === "locked") {
      return <span className="ml-auto flex items-center gap-1 rounded-full bg-brand-soft px-2 py-0.5 text-xs font-medium text-brand-ink">
        <LockIcon className="size-3" /> Ultra
      </span>;
    }
    return <span className="ml-auto flex items-center gap-1 text-xs text-muted-foreground"><SparklesIcon className="size-3" /> {d.generate}</span>;
  }

  const videos = items.filter((i) => i.format === "mp4");
  const audio = items.find((i) => i.format === "mp3");

  return (
    <div className={cn("flex", className)}>
      <a href={mainUrl} download className={buttonVariants({ variant: "outline", className: "flex-1 rounded-r-none" })}>
        <DownloadIcon /> MP4
      </a>
      <DropdownMenu open={open} onOpenChange={setOpen}>
        <DropdownMenuTrigger
          aria-label={t.clip.moreDownloads}
          className={buttonVariants({ variant: "outline", size: "icon", className: "rounded-l-none border-l-0" })}
        >
          {pending ? <Loader2Icon className="animate-spin" /> : <ChevronDownIcon />}
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-60">
          <DropdownMenuGroup>
            <DropdownMenuLabel>{d.video}</DropdownMenuLabel>
            {videos.length === 0 && (
              <DropdownMenuItem disabled><Loader2Icon className="animate-spin" /> {d.loading}</DropdownMenuItem>
            )}
            {videos.map((item) => (
              <DropdownMenuItem key={item.quality} closeOnClick={item.status === "ready"} onClick={() => pick(item)}>
                {item.status === "ready" ? <CheckIcon className="text-brand-ink" /> : <FilmIcon />}
                <span>
                  {label(item)}
                  {item.quality === "1080p" && <span className="text-muted-foreground"> · {d.original}</span>}
                </span>
                {status(item)}
              </DropdownMenuItem>
            ))}
          </DropdownMenuGroup>
          {audio && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuGroup>
                <DropdownMenuLabel>{d.audio}</DropdownMenuLabel>
                <DropdownMenuItem onClick={() => pick(audio)} disabled={request.isPending}>
                  <MusicIcon /> {d.mp3}
                  {request.isPending && request.variables?.format === "mp3"
                    ? <Loader2Icon className="ml-auto animate-spin" />
                    : status(audio)}
                </DropdownMenuItem>
              </DropdownMenuGroup>
            </>
          )}
          {cover && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuGroup>
                <DropdownMenuLabel>{d.cover}</DropdownMenuLabel>
                {cover.vertical_download_url && (
                  <DropdownMenuItem onClick={() => downloadUrl(cover.vertical_download_url!)}>
                    <ImageIcon /> {d.coverVertical}
                  </DropdownMenuItem>
                )}
                {cover.horizontal_download_url && (
                  <DropdownMenuItem onClick={() => downloadUrl(cover.horizontal_download_url!)}>
                    <ImageIcon /> {d.coverHorizontal}
                  </DropdownMenuItem>
                )}
              </DropdownMenuGroup>
            </>
          )}
          <DropdownMenuSeparator />
          <DropdownMenuGroup>
            <DropdownMenuLabel>{d.captions}</DropdownMenuLabel>
            <DropdownMenuItem onClick={() => downloadCaptions("srt")}><CaptionsIcon /> {t.clip.srt}</DropdownMenuItem>
            <DropdownMenuItem onClick={() => downloadCaptions("vtt")}><CaptionsIcon /> {t.clip.vtt}</DropdownMenuItem>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
