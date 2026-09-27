"use client";

import Link from "next/link";
import { CheckIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { usePlans } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";

const euros = new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

export function Pricing() {
  const { data: plans, isPending, error } = usePlans();

  if (error) return <p className="text-center text-sm text-muted-foreground">No se pudieron cargar los planes.</p>;
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
                {plan.name}
                {featured && <Badge>Más popular</Badge>}
              </CardTitle>
              <CardDescription>
                <span className="text-3xl font-semibold text-foreground">{euros.format(plan.price_eur_cents / 100)}</span>
                {!free && " /mes"}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="flex flex-col gap-2 text-sm">
                {[
                  `${plan.monthly_minutes} minutos de vídeo al mes`,
                  `Vídeos de hasta ${plan.max_video_minutes} min`,
                  `Hasta ${plan.max_clips_per_job} clips por vídeo`,
                  `${plan.max_concurrent_jobs} ${plan.max_concurrent_jobs === 1 ? "vídeo" : "vídeos"} a la vez`,
                  `Clips disponibles ${plan.retention_days} días`,
                ].map((feature) => (
                  <li key={feature} className="flex gap-2">
                    <CheckIcon className="mt-0.5 size-4 shrink-0 text-primary" />
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
                {free ? "Empezar gratis" : "Próximamente"}
              </Link>
            </CardFooter>
          </Card>
        );
      })}
    </div>
  );
}
