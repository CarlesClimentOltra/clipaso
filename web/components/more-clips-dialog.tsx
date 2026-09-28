"use client";

import { SparklesIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Segmented } from "@/components/segmented";
import { Button } from "@/components/ui/button";
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
import { ApiError, type Job } from "@/lib/api/client";
import { useMoreClips } from "@/lib/api/hooks";
import { useI18n } from "@/lib/i18n";

export function MoreClipsDialog({ job, maxPerRequest }: { job: Job; maxPerRequest: number }) {
  const more = useMoreClips(job.id);
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const limit = Math.max(1, Math.min(job.more_clips_available, maxPerRequest));
  const [count, setCount] = useState(String(Math.min(3, limit)));
  const [topic, setTopic] = useState("");
  const searching = !!job.more_clips_task && ["queued", "running"].includes(job.more_clips_task.status);

  async function submit() {
    try {
      await more.mutateAsync({ count: Number(count), topic });
      toast.success(t.more.started);
      setOpen(false);
      setTopic("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : t.more.error);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant="outline" size="sm" className="h-9 rounded-full px-4" disabled={searching || job.more_clips_available <= 0} />}>
        <SparklesIcon /> {t.more.button}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t.more.title}</DialogTitle>
          <DialogDescription>
            {t.more.text}
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label>{t.more.howMany}</Label>
            <Segmented
              label={t.more.countLabel}
              value={count}
              onChange={setCount}
              options={Array.from({ length: limit }, (_, i) => ({ value: String(i + 1), label: String(i + 1) }))}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="more-topic">
              {t.options.topic} <span className="font-normal text-muted-foreground">{t.common.optional}</span>
            </Label>
            <Input id="more-topic" maxLength={200} value={topic} onChange={(e) => setTopic(e.target.value)}
                   placeholder={t.more.topicPlaceholder} />
          </div>
        </div>
        <DialogFooter>
          <DialogClose render={<Button variant="outline" />}>{t.common.cancel}</DialogClose>
          <Button onClick={submit} disabled={more.isPending}>
            {more.isPending ? t.more.sending : t.more.submit}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
