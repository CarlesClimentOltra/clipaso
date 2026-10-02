"use client";

import Link from "next/link";
import { useState } from "react";
import { CheckIcon, Loader2Icon } from "lucide-react";
import { toast } from "sonner";
import { track } from "@vercel/analytics";
import { useQueryClient } from "@tanstack/react-query";

import { toastError } from "@/components/error-toast";
import { Segmented } from "@/components/segmented";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import type { Plan } from "@/lib/api/client";
import { useBillingConfig, useChangePlan, useMe, usePlans } from "@/lib/api/hooks";
import { useI18n } from "@/lib/i18n";
import { openCheckout } from "@/lib/paddle";
import { cn } from "@/lib/utils";

type Interval = "month" | "year";
type PaidPlan = "pro" | "ultra";

/**
 * Planes con sus precios (mensual o anual con un 20 % menos). Con `current` (dentro de la app) marca el plan
 * del usuario y ofrece mejorar: pago con Paddle si no tiene suscripción, o cambio de plan si ya la tiene.
 */
export function Pricing({ current }: { current?: string } = {}) {
  const { data: plans, isPending, error } = usePlans();
  const { t, intl, locale } = useI18n();
  const p = t.pricing;
  const pp = t.plansPage;
  const inApp = current !== undefined;
  const { data: me } = useMe();
  const { data: config } = useBillingConfig();
  const change = useChangePlan();
  const qc = useQueryClient();
  const [interval, setInterval_] = useState<Interval>(me?.billing?.interval ?? "month");
  const [pending, setPending] = useState<{ plan: PaidPlan; interval: Interval } | null>(null);
  const [opening, setOpening] = useState<string | null>(null);
  const euros = new Intl.NumberFormat(intl, { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
  const eurosCents = new Intl.NumberFormat(intl, { style: "currency", currency: "EUR", maximumFractionDigits: 2 });
  const subscribed = !!me?.billing && ["active", "trialing", "past_due"].includes(me.billing.status ?? "");
  const name = (code: string) => t.plans[code] ?? code;
  const period = (i: Interval) => (i === "year" ? p.yearly : p.monthly).toLowerCase();

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

  /** Tras pagar, el webhook de Paddle cambia el plan en unos segundos: se consulta /me hasta verlo. */
  function waitForPlan(plan: string) {
    toast.info(pp.paid);
    let tries = 0;
    const timer = window.setInterval(async () => {
      tries += 1;
      await qc.invalidateQueries({ queryKey: ["me"] });
      const fresh = qc.getQueryData<{ plan: { code: string } }>(["me"]);
      if (fresh?.plan.code === plan || tries >= 20) {
        window.clearInterval(timer);
        if (fresh?.plan.code === plan) toast.success(pp.activated);
      }
    }, 2000);
  }

  async function checkout(plan: PaidPlan) {
    const priceId = config?.prices[`${plan}_${interval}`];
    if (!config?.enabled || !priceId || !me) return;
    track("upgrade_click", { plan, interval });
    setOpening(plan);
    try {
      await openCheckout({
        environment: config.environment,
        token: config.client_token,
        priceId,
        email: me.email,
        userId: me.id,
        locale,
        onEvent: (event) => {
          if (event === "checkout.completed") waitForPlan(plan);
        },
      });
    } catch {
      toast.error(pp.payError);
    } finally {
      setOpening(null);
    }
  }

  async function confirmChange() {
    if (!pending) return;
    try {
      await change.mutateAsync(pending);
      toast.success(pp.changed);
      setPending(null);
    } catch (err) {
      toastError(err, pp.payError);
    }
  }

  function action(plan: Plan, featured: boolean) {
    const free = plan.price_eur_cents === 0;
    if (!inApp) {
      return (
        <Link href="/login" className={buttonVariants({ variant: featured ? "default" : "outline", className: "w-full" })}>
          {free ? p.startFree : p.start}
        </Link>
      );
    }
    const mine = current === plan.code;
    if (free) {
      return mine ? <Button variant="outline" className="w-full" disabled>{pp.currentButton}</Button> : null;
    }
    const code = plan.code as PaidPlan;
    if (mine && (!subscribed || me?.billing?.interval === interval)) {
      return <Button variant="outline" className="w-full" disabled>{pp.currentButton}</Button>;
    }
    if (!config?.enabled) {
      return (
        <Button className="w-full" onClick={() => {
          track("upgrade_click", { plan: code });
          toast.info(pp.soonHint);
        }}>
          {pp.upgrade} · {pp.soon}
        </Button>
      );
    }
    if (subscribed) {
      const label = mine ? (interval === "year" ? pp.toYearly : pp.toMonthly) : pp.changeTo(name(code));
      return (
        <Button className="w-full" variant={mine ? "outline" : "default"} onClick={() => setPending({ plan: code, interval })}>
          {label}
        </Button>
      );
    }
    return (
      <Button className="w-full" onClick={() => checkout(code)} disabled={opening !== null}>
        {opening === code && <Loader2Icon className="animate-spin" />} {pp.upgradeTo(name(code))}
      </Button>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-center gap-3">
        <Segmented<Interval>
          label={p.yearly}
          value={interval}
          onChange={setInterval_}
          options={[
            { value: "month", label: p.monthly },
            { value: "year", label: <>{p.yearly} <span className="ml-1 font-semibold text-brand-ink">{p.save}</span></> },
          ]}
        />
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {plans.map((plan, i) => {
          const featured = i === 1;
          const free = plan.price_eur_cents === 0;
          const mine = current === plan.code;
          const yearly = interval === "year" && !free;
          const amount = yearly ? plan.price_eur_cents_yearly : plan.price_eur_cents;
          return (
            <Card key={plan.code} className={cn((inApp ? mine : featured) && "ring-2 ring-primary")}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  {name(plan.code)}
                  {mine ? <Badge>{pp.current}</Badge> : featured && !inApp && <Badge>{p.popular}</Badge>}
                </CardTitle>
                <CardDescription>
                  <span className="text-3xl font-semibold text-foreground">{euros.format(amount / 100)}</span>
                  {!free && (yearly ? p.perYear : p.perMonth)}
                  {yearly && (
                    <span className="mt-1 block text-xs">{p.yearlyEquivalent(eurosCents.format(amount / 1200))}</span>
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="flex flex-col gap-2 text-sm">
                  {[
                    p.minutesMonth(plan.monthly_minutes),
                    p.allModes,
                    p.maxVideo(plan.max_video_minutes, plan.max_upload_mb >= 1024
                      ? `${Math.round(plan.max_upload_mb / 1024)} GB` : `${plan.max_upload_mb} MB`),
                    p.maxClips(plan.max_clips_per_job, plan.max_clips_per_project),
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
              <CardFooter className="mt-auto">{action(plan, featured)}</CardFooter>
            </Card>
          );
        })}
      </div>

      <Dialog open={pending !== null} onOpenChange={(open) => !open && setPending(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{pp.confirmTitle}</DialogTitle>
            <DialogDescription>
              {pending && pp.confirmText(name(pending.plan), period(pending.interval))}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose render={<Button variant="outline" />}>{pp.cancel}</DialogClose>
            <Button onClick={confirmChange} disabled={change.isPending}>
              {change.isPending && <Loader2Icon className="animate-spin" />} {pp.confirm}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
