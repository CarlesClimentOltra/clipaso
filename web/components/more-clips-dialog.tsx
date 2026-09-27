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

export function MoreClipsDialog({ job, maxPerRequest }: { job: Job; maxPerRequest: number }) {
  const more = useMoreClips(job.id);
  const [open, setOpen] = useState(false);
  const limit = Math.max(1, Math.min(job.more_clips_available, maxPerRequest));
  const [count, setCount] = useState(String(Math.min(3, limit)));
  const [topic, setTopic] = useState("");
  const searching = !!job.more_clips_task && ["queued", "running"].includes(job.more_clips_task.status);

  async function submit() {
    try {
      await more.mutateAsync({ count: Number(count), topic });
      toast.success("Buscando más momentos en tu vídeo…");
      setOpen(false);
      setTopic("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo pedir más clips.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant="outline" size="sm" disabled={searching || job.more_clips_available <= 0} />}>
        <SparklesIcon /> Más clips
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Buscar más clips en este vídeo</DialogTitle>
          <DialogDescription>
            Usamos el vídeo que ya subiste, así que no gasta minutos de tu plan. No repetiremos los momentos que ya
            tienes.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label>¿Cuántos?</Label>
            <Segmented
              label="Número de clips"
              value={count}
              onChange={setCount}
              options={Array.from({ length: limit }, (_, i) => ({ value: String(i + 1), label: String(i + 1) }))}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="more-topic">
              Tema <span className="font-normal text-muted-foreground">(opcional)</span>
            </Label>
            <Input id="more-topic" maxLength={200} value={topic} onChange={(e) => setTopic(e.target.value)}
                   placeholder="Por ejemplo: los consejos prácticos" />
          </div>
        </div>
        <DialogFooter>
          <DialogClose render={<Button variant="outline" />}>Cancelar</DialogClose>
          <Button onClick={submit} disabled={more.isPending}>
            {more.isPending ? "Enviando…" : "Buscar clips"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
