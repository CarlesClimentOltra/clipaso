"use client";

import { Progress } from "@/components/ui/progress";
import type { Me } from "@/lib/api/client";
import { cn } from "@/lib/utils";

export function formatMinutes(minutes: number): string {
  return `${Number.isInteger(minutes) ? minutes : minutes.toFixed(1)} min`;
}

export function UsageMeter({ me, className }: { me: Me; className?: string }) {
  const { used_minutes, limit_minutes } = me.usage;
  const pct = limit_minutes > 0 ? Math.min(100, (used_minutes / limit_minutes) * 100) : 100;
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <div className="flex items-baseline justify-between gap-3 text-xs whitespace-nowrap">
        <span className="text-muted-foreground">Este mes</span>
        <span className="font-medium tabular-nums">
          {formatMinutes(used_minutes)} / {formatMinutes(limit_minutes)}
        </span>
      </div>
      <Progress value={pct} aria-label="Minutos consumidos este mes" className={pct >= 90 ? "[&_[data-slot=progress-indicator]]:bg-destructive" : undefined} />
    </div>
  );
}
