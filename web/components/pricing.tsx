"use client";

import Link from "next/link";
import { CheckIcon } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { usePlans } from "@/lib/api/hooks";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";


/** Planes con sus precios. Con `current` (dentro de la app) marca el plan del usuario y ofrece mejorar. */
export function Pricing({ current }: { current?: string } = {}) {
  const { data: plans, isPending, error } = usePlans();
  const { t, intl } = useI18n();
  const p = t.pricing;
  const euros = new Intl.NumberFormat(intl, { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

  if (error) return <p className="text-center text-sm text-muted-foreground">{p.loadError}</p>;
  if (isPending) {
    return (
      <div className="grid gap-4 md:grid-cols-3">
        {Array.from({ length: 3 }, (_, i) => (
          <Skeleton key={i} className="h-80 rounded-xl" />
        ))}
      </div>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-3">
      {plans.map((plan, i) => {
        const featured = i === 1;
        const free = plan.price_eur_cents === 0;
        const mine = current === plan.code;
        // Sin plan público (cuenta de desarrollo o aún cargando) no se ofrece mejorar.
        const currentPrice = plans.find((x) => x.code === current)?.price_eur_cents ?? Infinity;
        return (
          <Card key={plan.code} className={cn((current ? mine : featured) && "ring-2 ring-primary")}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {t.plans[plan.code] ?? plan.name}
                {mine ? <Badge>{t.plansPage.current}</Badge> : featured && !current && <Badge>{p.popular}</Badge>}
              </CardTitle>
              <CardDescription>
                <span className="text-3xl font-semibold text-foreground">{euros.format(plan.price_eur_cents / 100)}</span>
                {!free && p.perMonth}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="flex flex-col gap-2 text-sm">
                {[
                  p.minutesMonth(plan.monthly_minutes),
                  p.allModes,
                  p.maxVideo(plan.max_video_minutes, plan.max_upload_mb >= 1024
                    ? `${Math.round(plan.max_upload_mb / 1024)} GB` : `${plan.max_upload_mb} MB`),
                  p.maxClips(plan.max_clips_per_job),
                  plan.watermark ? p.withWatermark : p.noWatermark,
                  plan.max_export_quality === "2160p" ? p.quality4k : p.quality1080,
                  p.thumbnails(plan.daily_thumbnails),
                  p.daily(plan.daily_renders, plan.daily_more_clips, plan.daily_exports, plan.daily_covers),
                  p.concurrent(plan.max_concurrent_jobs),
                  p.retention(plan.retention_days),
                ].map((feature) => (
                  <li key={feature} className="flex gap-2">
                    <CheckIcon className="mt-0.5 size-4 shrink-0 text-brand-ink" />
                    {feature}
                  </li>
                ))}
              </ul>
            </CardContent>
            <CardFooter className="mt-auto">
              {current === undefined ? (
                <Link
                  href="/login"
                  className={buttonVariants({ variant: featured ? "default" : "outline", className: "w-full" })}
                >
                  {free ? p.startFree : p.soon}
                </Link>
              ) : mine ? (
                <Button variant="outline" className="w-full" disabled>{t.plansPage.currentButton}</Button>
              ) : plan.price_eur_cents > currentPrice ? (
                // Sin pasarela de pago todavía: con Stripe, este botón llevará al pago.
                <Button className="w-full" onClick={() => toast.info(t.plansPage.soonHint)}>
                  {t.plansPage.upgrade} · {t.plansPage.soon}
                </Button>
              ) : null}
            </CardFooter>
          </Card>
        );
      })}
    </div>
  );
}
