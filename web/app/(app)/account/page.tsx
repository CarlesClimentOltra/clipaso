"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Trash2Icon } from "lucide-react";
import { toast } from "sonner";

import { AccountSecurity } from "@/components/account-security";
import { BrandSettings } from "@/components/brand-settings";
import { CaptionStylesSettings } from "@/components/caption-styles-settings";
import { PageHeader } from "@/components/page-header";
import { UsageMeter } from "@/components/usage-meter";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/client";
import { useDeleteAccount, useMe } from "@/lib/api/hooks";
import { useAuth } from "@/lib/auth";
import { config } from "@/lib/config";
import { useI18n, type Locale } from "@/lib/i18n";
import { Segmented } from "@/components/segmented";

export default function AccountPage() {
  const { session, signOut } = useAuth();
  const { data: me } = useMe();
  const remove = useDeleteAccount();
  const router = useRouter();
  const [confirmation, setConfirmation] = useState("");
  const email = session?.email ?? "";
  const confirmed = confirmation.trim().toLowerCase() === email.toLowerCase() && email !== "";
  const { t, locale, setLocale } = useI18n();
  const a = t.account;

  async function onDelete() {
    try {
      await remove.mutateAsync();
      await signOut().catch(() => {}); // la cuenta ya no existe: basta con olvidar la sesión local
      toast.success(a.deleted);
      router.replace("/");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : a.deleteError);
    }
  }

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <PageHeader eyebrow={a.eyebrow} title={a.title} description={a.lead} />

      <Card>
        <CardHeader>
          <CardTitle>{a.dataTitle}</CardTitle>
          <CardDescription>{a.dataLead}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 text-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-muted-foreground">{a.email}</span>
            <span className="font-medium">{email}</span>
          </div>
          {me && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-muted-foreground">{a.plan}</span>
                <Badge variant="secondary">{t.plans[me.plan.code] ?? me.plan.name}</Badge>
              </div>
              <UsageMeter me={me} />
            </>
          )}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="flex flex-col">
              <span className="text-muted-foreground">{t.common.language}</span>
              <span className="text-xs text-muted-foreground">{a.languageHint}</span>
            </span>
            <Segmented<Locale>
              label={t.common.language}
              value={locale}
              onChange={setLocale}
              options={[
                { value: "es", label: "Español" },
                { value: "en", label: "English" },
              ]}
            />
          </div>
        </CardContent>
      </Card>

      <CaptionStylesSettings />

      <BrandSettings />

      {config.authMode === "supabase" && <AccountSecurity />}

      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle>{a.deleteTitle}</CardTitle>
          <CardDescription>
            {a.deleteLead}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Dialog onOpenChange={(open) => !open && setConfirmation("")}>
            <DialogTrigger render={<Button variant="destructive" />}>
              <Trash2Icon /> {a.deleteButton}
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{a.deleteDialogTitle}</DialogTitle>
                <DialogDescription>
                  {a.deleteDialogText}
                </DialogDescription>
              </DialogHeader>
              <div className="flex flex-col gap-2">
                <Label htmlFor="confirm-email">
                  {a.confirmEmail} <span className="font-medium">{email}</span>
                </Label>
                <Input
                  id="confirm-email"
                  type="email"
                  autoComplete="off"
                  value={confirmation}
                  onChange={(e) => setConfirmation(e.target.value)}
                />
              </div>
              <DialogFooter>
                <DialogClose render={<Button variant="outline" />}>{t.common.cancel}</DialogClose>
                <Button variant="destructive" onClick={onDelete} disabled={!confirmed || remove.isPending}>
                  {remove.isPending ? a.deleting : a.deleteConfirm}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          <p className="mt-4 text-xs text-muted-foreground">
            {a.moreInfo} <Link href="/legal/privacidad" className="underline underline-offset-4">{a.privacy}</Link>.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
