"use client";

import Link from "next/link";
import { CheckIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { usePlans } from "@/lib/api/hooks";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";


export function Pricing() {
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
        return (
          <Card key={plan.code} className={cn(featured && "ring-2 ring-primary")}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {t.plans[plan.code] ?? plan.name}
                {featured && <Badge>{p.popular}</Badge>}
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
                  p.maxVideo(plan.max_video_minutes),
                  p.maxClips(plan.max_clips_per_job),
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
              <Link
                href="/login"
                className={buttonVariants({ variant: featured ? "default" : "outline", className: "w-full" })}
              >
                {free ? p.startFree : p.soon}
              </Link>
            </CardFooter>
          </Card>
        );
      })}
    </div>
  );
}
