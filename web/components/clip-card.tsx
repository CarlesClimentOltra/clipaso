"use client";

import { DownloadIcon } from "lucide-react";

import { ClipPlayer } from "@/components/clip-player";
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
      <ClipPlayer src={clip.video_url} poster={clip.thumbnail_url ?? undefined} title={clip.title} rank={clip.rank} />
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
