"use client";

import {
  CopyIcon,
  EllipsisIcon,
  PencilIcon,
  PlusIcon,
  RotateCcwIcon,
  StarIcon,
  Trash2Icon,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { CaptionPreview, type ClipFormat } from "@/components/caption-preview";
import { ONBOARDING_FLAGS } from "@/components/onboarding-checklist";
import { Segmented } from "@/components/segmented";
import { StyleEditor } from "@/components/style-editor";
import { useStyleName } from "@/components/style-picker";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, type CaptionStyle, type UserStyle } from "@/lib/api/client";
import { useStyleActions, useStyles } from "@/lib/api/hooks";
import { setFlag } from "@/lib/flags";
import { useI18n } from "@/lib/i18n";

type Draft = { id: string | null; name: string; style: CaptionStyle; builtin: boolean };

/** Diálogo para crear o editar un estilo con vista previa grande y animada. */
function StyleDialog({ draft, onClose }: { draft: Draft | null; onClose: () => void }) {
  const { t } = useI18n();
  const s = t.styles;
  const actions = useStyleActions();
  const [value, setValue] = useState<Draft | null>(draft);
  const [format, setFormat] = useState<ClipFormat>("vertical");
  const [prev, setPrev] = useState(draft);
  if (draft !== prev) {
    setPrev(draft);
    setValue(draft);
  }
  const pending = actions.create.isPending || actions.update.isPending;

  async function save() {
    if (!value) return;
    try {
      if (value.id) await actions.update.mutateAsync({ id: value.id, name: value.name, style: value.style });
      else await actions.create.mutateAsync({ name: value.name, style: value.style });
      setFlag(ONBOARDING_FLAGS.styled);
      toast.success(s.saved);
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : s.saveError);
    }
  }

  return (
    <Dialog open={!!draft} onOpenChange={(open: boolean) => !open && onClose()}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-hidden p-0 sm:max-w-5xl">
        {value && (
          <div className="grid max-h-[calc(100dvh-2rem)] md:grid-cols-[1fr_300px]">
            <div className="flex min-h-0 flex-col gap-5 overflow-y-auto p-5">
              <DialogHeader>
                <DialogTitle>{value.id ? s.editTitle : s.newTitle}</DialogTitle>
              </DialogHeader>
              <div className="flex flex-col gap-2">
                <Label htmlFor="style-name">{s.name}</Label>
                <Input id="style-name" maxLength={40} value={value.name} placeholder={s.namePlaceholder}
                       onChange={(e) => setValue({ ...value, name: e.target.value })} />
              </div>
              <StyleEditor value={value.style} onChange={(style) => setValue({ ...value, style })} />
            </div>
            <div className="flex flex-col gap-4 border-t bg-muted/40 p-5 md:border-t-0 md:border-l">
              <div className="flex flex-1 flex-col items-center justify-center gap-3">
                <CaptionPreview style={value.style} format={format} animate
                                className={format === "horizontal" ? "rounded-2xl" : "max-w-56 rounded-2xl"} />
                <Segmented label={s.previewFormat} value={format} onChange={setFormat}
                           options={[
                             { value: "vertical", label: "9:16" },
                             { value: "square", label: "1:1" },
                             { value: "horizontal", label: "16:9" },
                           ]} />
              </div>
              <DialogFooter className="mx-0 mb-0 border-0 bg-transparent p-0">
                <Button type="button" variant="ghost" onClick={onClose}>{t.common.cancel}</Button>
                <Button type="button" onClick={save} disabled={pending || !value.name.trim()}>
                  {pending ? t.common.saving : s.save}
                </Button>
              </DialogFooter>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function StyleTile({
  item,
  name,
  isDefault,
  canDuplicate,
  onEdit,
  onDuplicate,
}: {
  item: UserStyle;
  name: string;
  isDefault: boolean;
  canDuplicate: boolean;
  onEdit: () => void;
  onDuplicate: () => void;
}) {
  const { t } = useI18n();
  const s = t.styles;
  const actions = useStyleActions();
  const [hover, setHover] = useState(false);

  async function run(p: Promise<unknown>, ok: string) {
    try {
      await p;
      toast.success(ok);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : s.saveError);
    }
  }

  return (
    <div
      className="group relative flex flex-col gap-2 rounded-2xl border p-2 transition-colors hover:bg-muted/50"
      onPointerEnter={() => setHover(true)}
      onPointerLeave={() => setHover(false)}
    >
      <button type="button" onClick={onEdit} aria-label={`${t.common.edit} ${name}`}
              className="rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-ring/50">
        <CaptionPreview style={item.style} animate={hover} className="rounded-xl" />
      </button>
      <div className="flex items-start justify-between gap-1 px-0.5">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="truncate text-sm font-medium">{name}</span>
          <div className="flex flex-wrap gap-1">
            {isDefault && <Badge className="gap-1"><StarIcon className="size-3" />{s.default}</Badge>}
            {item.modified && <Badge variant="secondary">{s.modified}</Badge>}
            {!item.builtin && <Badge variant="outline">{s.own}</Badge>}
          </div>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger render={<Button variant="ghost" size="icon-sm" aria-label={s.actions} />}>
            <EllipsisIcon />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuItem onClick={onEdit}><PencilIcon /> {t.common.edit}</DropdownMenuItem>
            <DropdownMenuItem onClick={onDuplicate} disabled={!canDuplicate}><CopyIcon /> {s.duplicate}</DropdownMenuItem>
            {!isDefault && (
              <DropdownMenuItem onClick={() => run(actions.setDefault.mutateAsync(item.id), s.defaultSet)}>
                <StarIcon /> {s.makeDefault}
              </DropdownMenuItem>
            )}
            {(item.modified || !item.builtin) && <DropdownMenuSeparator />}
            {item.modified && (
              <DropdownMenuItem onClick={() => run(actions.remove.mutateAsync(item.id), s.resetDone)}>
                <RotateCcwIcon /> {s.reset}
              </DropdownMenuItem>
            )}
            {!item.builtin && (
              <DropdownMenuItem variant="destructive"
                                onClick={() => run(actions.remove.mutateAsync(item.id), s.deleted)}>
                <Trash2Icon /> {s.delete}
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}

/** Mi cuenta → estilos de subtítulos: modificar los de serie, crear los tuyos y elegir el predeterminado. */
export function CaptionStylesSettings() {
  const { data } = useStyles();
  const { t } = useI18n();
  const s = t.styles;
  const styleName = useStyleName();
  const [draft, setDraft] = useState<Draft | null>(null);
  const customCount = data?.styles.filter((u) => !u.builtin).length ?? 0;
  const full = !!data && customCount >= data.max_custom;
  const defaultStyle = data?.styles.find((u) => u.id === data.default_id);

  return (
    <Card id="estilos" className="scroll-mt-24">
      <CardHeader>
        <CardTitle>{s.manageTitle}</CardTitle>
        <CardDescription>{s.manageLead}</CardDescription>
        <CardAction className="flex flex-col items-end gap-1">
          <Button
            type="button"
            size="sm"
            disabled={!data || full}
            onClick={() => defaultStyle && setDraft({ id: null, name: "", style: defaultStyle.style, builtin: false })}
          >
            <PlusIcon /> {s.newStyle}
          </Button>
          {data && <span className="text-xs text-muted-foreground">{s.ownCount(customCount, data.max_custom)}</span>}
        </CardAction>
      </CardHeader>
      <CardContent>
        {data ? (
          <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-6">
            {data.styles.map((u) => (
              <StyleTile
                key={u.id}
                item={u}
                name={styleName(u)}
                isDefault={u.id === data.default_id}
                canDuplicate={!full}
                onEdit={() => setDraft({ id: u.id, name: styleName(u), style: u.style, builtin: u.builtin })}
                onDuplicate={() =>
                  setDraft({ id: null, name: s.copyOf(styleName(u)).slice(0, 40), style: u.style, builtin: false })
                }
              />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-6">
            {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="aspect-9/16 rounded-2xl" />)}
          </div>
        )}
      </CardContent>
      <StyleDialog draft={draft} onClose={() => setDraft(null)} />
    </Card>
  );
}
