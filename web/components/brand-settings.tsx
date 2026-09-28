"use client";

import { ImageUpIcon, Trash2Icon } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { CaptionPreview } from "@/components/caption-preview";
import { Segmented } from "@/components/segmented";
import { StylePicker } from "@/components/style-picker";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { ApiError, type BrandingPrefs, type CaptionStyle, type Preferences } from "@/lib/api/client";
import { useLogo, usePreferences, useSavePreferences } from "@/lib/api/hooks";
import { ONBOARDING_FLAGS } from "@/components/onboarding-checklist";
import { setFlag } from "@/lib/flags";
import { useI18n } from "@/lib/i18n";

const CORNERS = ["top-left", "top-right", "bottom-left", "bottom-right"] as const;

function BrandForm({ prefs }: { prefs: Preferences }) {
  const save = useSavePreferences();
  const { t } = useI18n();
  const b = t.brand;
  const logo = useLogo();
  const fileRef = useRef<HTMLInputElement>(null);
  const [style, setStyle] = useState<CaptionStyle>(prefs.caption_style);
  const [branding, setBranding] = useState<BrandingPrefs>(prefs.branding);
  const set = (patch: Partial<BrandingPrefs>) => setBranding({ ...branding, ...patch });
  const dirty =
    JSON.stringify(style) !== JSON.stringify(prefs.caption_style) ||
    branding.handle !== prefs.branding.handle ||
    branding.position !== prefs.branding.position ||
    branding.enabled !== prefs.branding.enabled;

  async function onSave() {
    try {
      await save.mutateAsync({ caption_style: style, branding });
      setFlag(ONBOARDING_FLAGS.styled);
      toast.success(b.saved);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : b.saveError);
    }
  }

  async function onLogo(file: File | undefined) {
    if (!file) return;
    if (file.size > 1024 * 1024) {
      toast.error(b.logoTooBig);
      return;
    }
    try {
      await logo.upload.mutateAsync(file);
      toast.success(b.logoSaved);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : b.logoError);
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <CardContent className="flex flex-col gap-6">
      <div className="grid gap-6 md:grid-cols-[1fr_180px]">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-3">
            <Label>{b.defaultStyle}</Label>
            <StylePicker value={style} onChange={setStyle} />
          </div>
          <Separator />
          <div className="flex items-center justify-between gap-3">
            <div>
              <Label htmlFor="brand-enabled">{b.personal}</Label>
              <p className="text-xs text-muted-foreground">{b.personalHint}</p>
            </div>
            <Switch id="brand-enabled" checked={branding.enabled ?? true}
                    onCheckedChange={(c: boolean) => set({ enabled: c })} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="brand-handle">{b.handle}</Label>
              <Input id="brand-handle" maxLength={30} placeholder={b.handlePlaceholder} value={branding.handle ?? ""}
                     onChange={(e) => set({ handle: e.target.value })} />
            </div>
            <div className="flex flex-col gap-2">
              <Label>{b.logo}</Label>
              <div className="flex items-center gap-2">
                {prefs.logo_url && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={prefs.logo_url} alt={b.logoAlt} className="h-8 max-w-24 rounded border bg-muted object-contain" />
                )}
                <input ref={fileRef} type="file" accept="image/png,image/jpeg" className="hidden"
                       onChange={(e) => onLogo(e.target.files?.[0])} />
                <Button type="button" variant="outline" size="sm" onClick={() => fileRef.current?.click()}
                        disabled={logo.upload.isPending}>
                  <ImageUpIcon /> {prefs.logo_url ? b.change : b.upload}
                </Button>
                {prefs.logo_url && (
                  <Button type="button" variant="ghost" size="icon-sm" aria-label={b.removeLogo}
                          onClick={() => logo.remove.mutate()} disabled={logo.remove.isPending}>
                    <Trash2Icon />
                  </Button>
                )}
              </div>
              <p className="text-xs text-muted-foreground">{b.logoHint}</p>
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <Label>{b.position}</Label>
            <Segmented label={b.positionLabel} value={branding.position ?? "top-right"}
                       onChange={(position) => set({ position })}
                       options={CORNERS.map((c) => ({ value: c, label: b.corners[c] }))} />
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-xs text-muted-foreground">{b.preview}</span>
          <CaptionPreview style={style} branding={branding} logoUrl={prefs.logo_url} />
        </div>
      </div>
      <Button type="button" className="self-start" onClick={onSave} disabled={!dirty || save.isPending}>
        {save.isPending ? t.common.saving : b.save}
      </Button>
    </CardContent>
  );
}

export function BrandSettings() {
  const { data: prefs } = usePreferences();
  const { t } = useI18n();
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t.brand.title}</CardTitle>
        <CardDescription>{t.brand.lead}</CardDescription>
      </CardHeader>
      {prefs ? <BrandForm prefs={prefs} /> : <CardContent><Skeleton className="h-60 w-full" /></CardContent>}
    </Card>
  );
}
