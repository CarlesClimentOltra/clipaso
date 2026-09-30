"use client";

import { useRouter } from "next/navigation";
import { Trash2Icon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ApiError } from "@/lib/api/client";
import { useDeleteClip, useDeleteJob } from "@/lib/api/hooks";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

function Confirm({ open, onOpenChange, title, text, onConfirm, pending }: {
  open: boolean; onOpenChange: (open: boolean) => void; title: string; text: string;
  onConfirm: () => void; pending: boolean;
}) {
  const { t } = useI18n();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{text}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose render={<Button variant="outline" />}>{t.common.cancel}</DialogClose>
          <Button variant="destructive" onClick={onConfirm} disabled={pending}>
            <Trash2Icon /> {t.project.deleteConfirm}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Papelera que borra un proyecto entero (con confirmación). `redirect`: volver a «Mis proyectos» al borrar. */
export function DeleteProjectButton({ jobId, redirect = false, className, label }: {
  jobId: string; redirect?: boolean; className?: string; label?: string;
}) {
  const { t } = useI18n();
  const p = t.project;
  const router = useRouter();
  const remove = useDeleteJob();
  const [open, setOpen] = useState(false);

  async function onConfirm() {
    try {
      await remove.mutateAsync(jobId);
      toast.success(p.deleted);
      setOpen(false);
      if (redirect) router.replace("/dashboard");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : p.deleteError);
    }
  }

  return (
    <>
      <Button type="button" variant="outline" size={label ? "default" : "icon"} aria-label={p.delete} title={p.delete}
              className={cn("shrink-0", className)}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setOpen(true);
              }}>
        <Trash2Icon /> {label}
      </Button>
      <Confirm open={open} onOpenChange={setOpen} title={p.deleteTitle} text={p.deleteText} onConfirm={onConfirm}
               pending={remove.isPending} />
    </>
  );
}

/** Papelera que borra un clip del proyecto (los demás clips se quedan). */
export function DeleteClipButton({ jobId, clipId, className }: { jobId: string; clipId: string; className?: string }) {
  const { t } = useI18n();
  const c = t.clip;
  const remove = useDeleteClip(jobId);
  const [open, setOpen] = useState(false);

  async function onConfirm() {
    try {
      await remove.mutateAsync(clipId);
      toast.success(c.deleted);
      setOpen(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : c.deleteError);
    }
  }

  return (
    <>
      <Button type="button" variant="outline" size="icon" aria-label={c.delete} title={c.delete}
              className={cn("shrink-0", className)} onClick={() => setOpen(true)}>
        <Trash2Icon />
      </Button>
      <Confirm open={open} onOpenChange={setOpen} title={c.deleteTitle} text={c.deleteText} onConfirm={onConfirm}
               pending={remove.isPending} />
    </>
  );
}
