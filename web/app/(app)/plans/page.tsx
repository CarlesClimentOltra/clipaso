"use client";

import { AlertTriangleIcon, ExternalLinkIcon, InfoIcon, Loader2Icon } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { Pricing } from "@/components/pricing";
import { UsageMeter } from "@/components/usage-meter";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { toastError } from "@/components/error-toast";
import type { Me } from "@/lib/api/client";
import { useBillingPortal, useMe } from "@/lib/api/hooks";
import { useI18n } from "@/lib/i18n";

export default function PlansPage() {
  const { data: me } = useMe();
  const { t } = useI18n();
  const p = t.plansPage;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader eyebrow={t.header.plans} title={p.title} description={p.lead} />
      {me && (
        <Card>
          <CardContent>
            <UsageMeter me={me} />
          </CardContent>
        </Card>
      )}
      {me?.billing && <Subscription me={me} />}
      {me?.plan.unlimited && (
        <Alert>
          <InfoIcon />
          <AlertDescription>{p.dev}</AlertDescription>
        </Alert>
      )}
      {/* Mientras carga /me, sin plan marcado ("" en vez de undefined para no mostrar «Empezar gratis»). */}
      <Pricing current={me?.plan.code ?? ""} />
      <p className="text-sm text-muted-foreground">{p.minutesNote}</p>
    </div>
  );
}

/** Estado de la suscripción de pago y acceso al portal de Paddle (tarjeta, facturas, cancelar). */
function Subscription({ me }: { me: Me }) {
  const { t, intl } = useI18n();
  const p = t.plansPage;
  const portal = useBillingPortal();
  const billing = me.billing!;
  const date = (iso: string) => new Date(iso).toLocaleDateString(intl, { day: "numeric", month: "long", year: "numeric" });
  const active = ["active", "trialing", "past_due"].includes(billing.status ?? "");
  if (!active) return null;

  async function open() {
    try {
      const { url } = await portal.mutateAsync();
      window.open(url, "_blank", "noopener");
    } catch (err) {
      toastError(err, p.portalError);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {p.subscription}
          <Badge variant="secondary">
            {t.plans[me.plan.code] ?? me.plan.name} · {billing.interval === "year" ? t.pricing.yearly : t.pricing.monthly}
          </Badge>
        </CardTitle>
        <CardDescription>{p.manageHint}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-sm">
          {billing.status === "past_due" ? (
            <p className="flex items-start gap-2 text-destructive">
              <AlertTriangleIcon className="mt-0.5 size-4 shrink-0" /> {p.pastDue}
            </p>
          ) : billing.cancels_at ? (
            <p>{p.cancels(date(billing.cancels_at))}</p>
          ) : billing.renews_at ? (
            <p>{p.renews(date(billing.renews_at))}</p>
          ) : null}
        </div>
        {billing.can_manage && (
          <Button variant="outline" onClick={open} disabled={portal.isPending}>
            {portal.isPending ? <Loader2Icon className="animate-spin" /> : <ExternalLinkIcon />} {p.manage}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
