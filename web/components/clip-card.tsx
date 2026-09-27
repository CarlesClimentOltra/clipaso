"use client";

import { DownloadIcon } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import type { Clip } from "@/lib/api/client";

export function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function ClipCard({ clip }: { clip: Clip }) {
  return (
    <Card className="overflow-hidden pt-0">
      <div className="relative aspect-[9/16] bg-black">
        <video
          src={clip.video_url}
          poster={clip.thumbnail_url ?? undefined}
          controls
          playsInline
          preload="none"
          className="size-full object-contain"
          aria-label={`Vista previa: ${clip.title}`}
        />
        <span className="pointer-events-none absolute top-2 left-2 rounded-md bg-black/60 px-2 py-0.5 text-xs font-medium text-white">
          #{clip.rank}
        </span>
      </div>
      <CardHeader>
        <CardTitle className="line-clamp-2 leading-snug">{clip.title}</CardTitle>
        {clip.reason && <CardDescription className="line-clamp-3">{clip.reason}</CardDescription>}
      </CardHeader>
      <CardContent className="text-xs text-muted-foreground">
        {Math.round(clip.duration)} s · del {formatTimestamp(clip.start)} al {formatTimestamp(clip.end)} del vídeo original
      </CardContent>
      <CardFooter className="mt-auto">
        <a href={clip.download_url} download className={buttonVariants({ variant: "outline", className: "w-full" })}>
          <DownloadIcon />
          Descargar MP4
        </a>
      </CardFooter>
    </Card>
  );
}
