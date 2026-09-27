"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeftIcon, RotateCcwIcon, Trash2Icon } from "lucide-react";
import { toast } from "sonner";

import { ClipCard } from "@/components/clip-card";
import { JobProgress } from "@/components/job-progress";
import { formatMinutes } from "@/components/usage-meter";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { useDeleteJob, useJob } from "@/lib/api/hooks";

const dateFmt = new Intl.DateTimeFormat("es-ES", { day: "numeric", month: "long" });

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: job, error, isPending } = useJob(id);
  const remove = useDeleteJob();

  if (isPending) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-8 w-72" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }
  if (error || !job) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <Alert variant="destructive">
        <AlertTitle>{notFound ? "Proyecto no encontrado" : "No se pudo cargar el proyecto"}</AlertTitle>
        <AlertDescription>
          {notFound ? "Puede que se haya borrado o que el enlace no sea correcto." : error?.message}{" "}
          <Link href="/dashboard" className="underline">Volver a mis proyectos</Link>
        </AlertDescription>
      </Alert>
    );
  }

  const active = job.status === "queued" || job.status === "running";

  async function onDelete() {
    try {
      await remove.mutateAsync(job!.id);
      toast.success("Proyecto borrado");
      router.replace("/dashboard");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo borrar el proyecto.");
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-3">
        <Link href="/dashboard" className={buttonVariants({ variant: "ghost", size: "sm", className: "self-start" })}>
          <ArrowLeftIcon /> Mis proyectos
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="truncate text-2xl font-semibold tracking-tight">{job.title}</h1>
            <p className="text-sm text-muted-foreground">
              {formatMinutes(job.video_minutes)} de vídeo
              {job.status === "done" && job.expires_at && ` · disponible hasta el ${dateFmt.format(new Date(job.expires_at))}`}
            </p>
          </div>
          {!active && (
            <Dialog>
              <DialogTrigger render={<Button variant="outline" size="sm" />}>
                <Trash2Icon /> Borrar
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>¿Borrar este proyecto?</DialogTitle>
                  <DialogDescription>
                    Se eliminarán el vídeo original y todos sus clips. Esta acción no se puede deshacer.
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <DialogClose render={<Button variant="outline" />}>Cancelar</DialogClose>
                  <Button variant="destructive" onClick={onDelete} disabled={remove.isPending}>
                    Borrar definitivamente
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}
        </div>
      </div>

      {active && (
        <Card>
          <CardContent>
            <JobProgress job={job} />
          </CardContent>
        </Card>
      )}

      {job.status === "failed" && (
        <Alert variant="destructive">
          <AlertTitle>No hemos podido procesar este vídeo</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-3">
            <span>{job.error_message}</span>
            <Link href="/new" className={buttonVariants({ variant: "outline", size: "sm" })}>
              <RotateCcwIcon /> Probar con otro vídeo
            </Link>
          </AlertDescription>
        </Alert>
      )}

      {job.status === "expired" && (
        <Alert>
          <AlertTitle>Los clips de este proyecto han caducado</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-3">
            <span>
              Tu plan conserva los clips durante un tiempo limitado y se han borrado automáticamente
              {job.expires_at ? ` el ${dateFmt.format(new Date(job.expires_at))}` : ""}. Si los necesitas, vuelve a subir el vídeo.
            </span>
            <Link href="/new" className={buttonVariants({ variant: "outline", size: "sm" })}>
              <RotateCcwIcon /> Crear un proyecto nuevo
            </Link>
          </AlertDescription>
        </Alert>
      )}

      {job.status === "done" && (
        <section className="flex flex-col gap-4" aria-labelledby="clips-title">
          <h2 id="clips-title" className="text-lg font-semibold">
            {job.clips.length} {job.clips.length === 1 ? "clip" : "clips"}, del mejor al menos destacado
          </h2>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {job.clips.map((clip) => (
              <ClipCard key={clip.id} clip={clip} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
