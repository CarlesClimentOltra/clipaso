"use client";

import { PlayIcon } from "lucide-react";
import { useRef, useState } from "react";

// Reproductor de clip: todo el vídeo es clicable. En escritorio, un <video controls> sin cargar
// solo reacciona al pequeño botón de la barra; aquí un clic en cualquier parte lo reproduce.
// Los controles nativos (pausa, volumen, pantalla completa) aparecen tras el primer clic.
export const CLIP_ASPECT = { vertical: "9 / 16", square: "1 / 1", horizontal: "16 / 9" } as const;

export function ClipPlayer({
  src,
  poster,
  title,
  rank,
  aspect = CLIP_ASPECT.vertical,
}: {
  src: string;
  poster?: string;
  title: string;
  rank: number;
  aspect?: string;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [started, setStarted] = useState(false);

  function start() {
    const video = videoRef.current;
    if (!video) return;
    setStarted(true);
    video.play().catch(() => {
      // Si el navegador bloquea la reproducción, al menos quedan los controles visibles.
    });
  }

  return (
    <div className="relative bg-black" style={{ aspectRatio: aspect }}>
      <video
        ref={videoRef}
        src={src}
        poster={poster}
        controls={started}
        playsInline
        preload="metadata"
        className="size-full object-contain"
        aria-label={`Clip ${rank}: ${title}`}
        onClick={started ? undefined : start}
      />
      {!started && (
        <button
          type="button"
          onClick={start}
          aria-label={`Reproducir clip ${rank}`}
          className="group absolute inset-0 flex items-center justify-center bg-black/10 transition-colors outline-none hover:bg-black/25 focus-visible:ring-3 focus-visible:ring-ring/60 focus-visible:ring-inset"
        >
          <span className="flex size-16 items-center justify-center rounded-full bg-white/90 text-black shadow-lg transition-transform group-hover:scale-110">
            <PlayIcon className="ml-1 size-7 fill-current" />
          </span>
        </button>
      )}
      <span className="pointer-events-none absolute top-2 left-2 rounded-md bg-black/60 px-2 py-0.5 text-xs font-medium text-white">
        #{rank}
      </span>
    </div>
  );
}
