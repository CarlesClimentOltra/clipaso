"use client";

import { Progress } from "@/components/ui/progress";
import type { Me } from "@/lib/api/client";
import { cn } from "@/lib/utils";

export function formatMinutes(minutes: number): string {
  return `${Number.isInteger(minutes) ? minutes : minutes.toFixed(1)} min`;
}

function usedPct(me: Me) {
  const { used_minutes, limit_minutes } = me.usage;
  return limit_minutes > 0 ? Math.min(100, (used_minutes / limit_minutes) * 100) : 100;
}

export function UsageMeter({ me, className }: { me: Me; className?: string }) {
  const { used_minutes, limit_minutes } = me.usage;
  const pct = usedPct(me);
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <div className="flex items-baseline justify-between gap-3 text-xs whitespace-nowrap">
        <span className="text-muted-foreground">Este mes</span>
        <span className="font-medium tabular-nums">
          {formatMinutes(used_minutes)} / {formatMinutes(limit_minutes)}
        </span>
      </div>
      <Progress value={pct} aria-label="Minutos consumidos este mes" className={pct >= 90 ? "**:data-[slot=progress-indicator]:bg-destructive" : undefined} />
    </div>
  );
}

/** Anillo de minutos consumidos; en rojo a partir del 90 %. */
export function UsageRing({ me, size = 40, stroke = 4, className }: {
  me: Me;
  size?: number;
  stroke?: number;
  className?: string;
}) {
  const pct = usedPct(me);
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className={cn("-rotate-90 shrink-0", className)}
         role="img" aria-label={`${Math.round(pct)} % de los minutos del mes usados`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" className="stroke-muted" strokeWidth={stroke} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} strokeLinecap="round"
              className={pct >= 90 ? "stroke-destructive" : "stroke-primary"}
              strokeDasharray={`${Math.max(pct, 2) / 100 * c} ${c}`} />
    </svg>
  );
}
