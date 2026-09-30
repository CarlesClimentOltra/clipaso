"use client";

import { InfoIcon } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { Pricing } from "@/components/pricing";
import { UsageMeter } from "@/components/usage-meter";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";
import { useMe } from "@/lib/api/hooks";
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
