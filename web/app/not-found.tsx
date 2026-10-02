"use client";

import Link from "next/link";

import { SiteFooter } from "@/components/site-footer";
import { StatusPage } from "@/components/status-page";
import { buttonVariants } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n";

export default function NotFound() {
  const { t } = useI18n();
  const s = t.status;
  return (
    <div className="flex flex-1 flex-col">
      <StatusPage code="404" title={s.notFoundTitle} text={s.notFoundText}>
        <Link href="/" className={buttonVariants()}>{s.home}</Link>
        <Link href="/dashboard" className={buttonVariants({ variant: "outline" })}>{s.projects}</Link>
      </StatusPage>
      <SiteFooter />
    </div>
  );
}
