"use client";

import { AudioLinesIcon, MessageCircleOffIcon, TimerIcon } from "lucide-react";

import type { Job } from "@/lib/api/client";
import { formatTime } from "@/lib/captions";
import { useI18n } from "@/lib/i18n";

/** Lo que se quitó en el modo «sin silencios»: tiempo ganado, pausas y muletillas. */
export function CleanSummary({ stats }: { stats: NonNullable<Job["clean_stats"]> }) {
  const { t } = useI18n();
  const c = t.clean;
  const after = Math.max(0, stats.original_seconds - stats.removed_seconds);
  const pct = stats.original_seconds ? Math.round((stats.removed_seconds / stats.original_seconds) * 100) : 0;
  const nothing = stats.removed_seconds < 0.5;

  return (
    <section className="relative isolate overflow-hidden rounded-[2rem] border bg-card p-5 sm:p-7"
             aria-label={c.summaryLabel}>
      <div className="absolute -top-20 -right-10 -z-10 size-60 rounded-full bg-brand-soft blur-3xl" />
      {nothing ? (
        <p className="text-sm text-muted-foreground">{c.nothing}</p>
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-sm text-muted-foreground">{c.saved}</p>
              <p className="text-4xl font-semibold tracking-tight tabular-nums">
                −{formatTime(stats.removed_seconds)}{" "}
                <span className="text-base font-medium text-brand-ink">({pct}%)</span>
              </p>
            </div>
            <p className="flex items-center gap-2 text-sm tabular-nums">
              <TimerIcon className="size-4 text-brand-ink" />
              <span className="text-muted-foreground line-through">{formatTime(stats.original_seconds)}</span>
              →<strong>{formatTime(after)}</strong>
            </p>
          </div>
          <div className="h-2.5 overflow-hidden rounded-full bg-muted" aria-hidden>
            <div className="h-full rounded-full bg-primary" style={{ width: `${100 - pct}%` }} />
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="flex items-center gap-1.5 rounded-full border bg-background px-3 py-1">
              <AudioLinesIcon className="size-3.5 text-brand-ink" /> {c.pauses(stats.pauses)}
            </span>
            <span className="flex items-center gap-1.5 rounded-full border bg-background px-3 py-1">
              <MessageCircleOffIcon className="size-3.5 text-brand-ink" /> {c.fillers(stats.fillers)}
            </span>
          </div>
        </div>
      )}
    </section>
  );
}
