import type { Mode } from "@/lib/modes";
import { cn } from "@/lib/utils";

const WAVE = [5, 9, 14, 8, 2, 2, 2, 11, 16, 7, 12, 2, 2, 2, 2, 9, 15, 10, 6, 13, 8, 2, 2, 12, 7];

/** Ilustración de cada modo en su tarjeta de «Nuevo proyecto» (solo decorativa). */
export function ModeArt({ mode, className }: { mode: Mode; className?: string }) {
  return (
    <div aria-hidden className={cn(
      "relative flex items-center justify-center overflow-hidden bg-slate-950 bg-[radial-gradient(circle_at_20%_0%,rgba(190,242,100,0.22),transparent_55%)]",
      className,
    )}>
      {mode === "clips" && (
        <div className="flex items-end gap-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className={cn("relative flex aspect-9/16 w-14 flex-col justify-end rounded-lg border border-white/15 bg-white/10 p-1.5 transition-transform duration-300",
                                       i === 1 ? "w-16 -translate-y-2 group-hover:-translate-y-4" : "group-hover:-translate-y-1")}>
              <span className="mx-auto mb-1 h-1.5 w-8 rounded-full bg-lime-300" />
              <span className="mx-auto h-1.5 w-6 rounded-full bg-white/70" />
            </div>
          ))}
        </div>
      )}
      {mode === "subtitle" && (
        <div className="relative flex aspect-video w-44 flex-col items-center justify-end gap-1.5 rounded-lg border border-white/15 bg-white/10 pb-3">
          <span className="flex gap-1.5">
            <span className="h-2 w-8 rounded-full bg-white/80" />
            <span className="h-2 w-10 rounded-full bg-lime-300 transition-all duration-300 group-hover:w-12" />
            <span className="h-2 w-6 rounded-full bg-white/80" />
          </span>
          <span className="flex gap-1.5">
            <span className="h-2 w-12 rounded-full bg-white/80" />
            <span className="h-2 w-7 rounded-full bg-white/80" />
          </span>
        </div>
      )}
      {mode === "clean" && (
        <div className="flex h-16 items-center gap-1">
          {WAVE.map((h, i) => (
            <span key={i} style={{ height: `${h * 4}px` }}
                  className={cn("w-1.5 rounded-full transition-opacity duration-300",
                                h === 2 ? "bg-white/25 group-hover:opacity-0" : "bg-lime-300")} />
          ))}
        </div>
      )}
      {mode === "reframe" && (
        <div className="flex items-center gap-4">
          <div className="aspect-9/16 w-14 rounded-lg border border-white/15 bg-white/10 p-1.5">
            <div className="mx-auto mt-6 size-5 rounded-full bg-lime-300/80" />
          </div>
          <span className="flex gap-1">
            {[0, 1, 2].map((i) => (
              <span key={i} className="size-1.5 rounded-full bg-white/40 transition-colors duration-300 group-hover:bg-lime-300"
                    style={{ transitionDelay: `${i * 80}ms` }} />
            ))}
          </span>
          <div className="relative flex aspect-video w-36 items-center justify-center rounded-lg border border-white/15 bg-white/5">
            <div className="flex aspect-9/16 h-full items-start justify-center bg-white/10 pt-3">
              <div className="size-5 rounded-full bg-lime-300/80" />
            </div>
          </div>
        </div>
      )}
      {mode === "thumbnail" && (
        <div className="relative flex aspect-video w-44 flex-col justify-center gap-1.5 rounded-lg border border-white/15 bg-linear-to-br from-sky-500/60 to-fuchsia-500/50 p-3">
          <span className="h-4 w-24 rounded-sm bg-white shadow-[0_2px_0_#000]" />
          <span className="h-4 w-16 rounded-sm bg-yellow-300 shadow-[0_2px_0_#000] transition-all duration-300 group-hover:w-20" />
          <span className="absolute right-3 bottom-2 size-9 rounded-full border-2 border-white/70 bg-white/20" />
        </div>
      )}
    </div>
  );
}
