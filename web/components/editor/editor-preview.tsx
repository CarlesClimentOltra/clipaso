"use client";

import { PauseIcon, PlayIcon, RotateCcwIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { CaptionPreview, type ClipFormat } from "@/components/caption-preview";
import { Button } from "@/components/ui/button";
import type { CaptionStyle } from "@/lib/api/client";
import { captionAt, chunkWords, formatTime, type TimedWord } from "@/lib/captions";

/**
 * Reproduce solo el tramo elegido del original (versión ligera) con los subtítulos encima,
 * tal como quedarán. El encuadre es aproximado: el clip final sigue la cara de quien habla.
 */
export function EditorPreview({
  src,
  start,
  end,
  words,
  style,
  format,
}: {
  src: string;
  start: number;
  end: number;
  words: TimedWord[];
  style: CaptionStyle;
  format: ClipFormat;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(start);
  const chunks = useMemo(() => chunkWords(words.filter((w) => w.start >= start - 0.01 && w.end <= end + 0.01)),
    [words, start, end]);
  const caption = captionAt(chunks, time);

  // Al mover el recorte, el cabezal vuelve al inicio del tramo.
  useEffect(() => {
    const v = video.current;
    if (v && (v.currentTime < start || v.currentTime > end)) v.currentTime = start;
  }, [start, end]);

  function toggle() {
    const v = video.current;
    if (!v) return;
    if (playing) {
      v.pause();
      return;
    }
    if (v.currentTime < start || v.currentTime >= end - 0.05) v.currentTime = start;
    v.play().catch(() => setPlaying(false));
  }

  function restart() {
    const v = video.current;
    if (v) v.currentTime = start;
    setTime(start);
  }

  return (
    <div className="flex flex-col gap-3">
      <CaptionPreview
        style={style}
        format={format}
        words={caption?.words ?? []}
        activeIndex={caption?.active ?? -1}
        className="mx-auto rounded-2xl"
        background={
          <video
            ref={video}
            src={src}
            preload="auto"
            playsInline
            className="absolute inset-0 size-full object-cover"
            onLoadedMetadata={(e) => (e.currentTarget.currentTime = start)}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onTimeUpdate={(e) => {
              const v = e.currentTarget;
              setTime(v.currentTime);
              if (v.currentTime >= end) {
                v.pause();
                v.currentTime = start;
              }
            }}
          />
        }
      />
      <div className="flex items-center justify-center gap-2">
        <Button type="button" size="icon" variant="outline" onClick={restart} aria-label="Volver al inicio del clip">
          <RotateCcwIcon />
        </Button>
        <Button type="button" onClick={toggle} className="min-w-28">
          {playing ? <PauseIcon /> : <PlayIcon />}
          {playing ? "Pausa" : "Reproducir"}
        </Button>
        <span className="min-w-24 text-center text-sm tabular-nums text-muted-foreground">
          {formatTime(Math.max(0, time - start))} / {formatTime(end - start)}
        </span>
      </div>
      <p className="text-center text-xs text-muted-foreground">
        Vista aproximada: en el clip final el encuadre sigue la cara de quien habla.
      </p>
    </div>
  );
}
