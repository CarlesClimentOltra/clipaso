"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";

import {
  ApiError,
  createApi,
  unwrap,
  type Api,
  type BrandingPrefs,
  type CaptionStyle,
  type Clip,
  type Job,
  type JobOptions,
  type UserStyles,
} from "@/lib/api/client";
import { uploadFile, type UploadProgress } from "@/lib/api/multipart-upload";
import { useAuth } from "@/lib/auth";
import { dictionary, useI18n } from "@/lib/i18n";
import { getStoredLocale } from "@/lib/i18n/store";

const ACTIVE = new Set(["queued", "running"]);

export function useApi(): Api {
  const { getToken } = useAuth();
  return useMemo(() => createApi(getToken), [getToken]);
}

export function useMe() {
  const api = useApi();
  const { session } = useAuth();
  return useQuery({
    queryKey: ["me"],
    queryFn: () => unwrap(api.GET("/me")),
    enabled: !!session,
  });
}

export function usePlans() {
  const api = useApi();
  return useQuery({ queryKey: ["plans"], queryFn: () => unwrap(api.GET("/plans")), staleTime: 60 * 60_000 });
}

export function useJobs() {
  const api = useApi();
  const { session } = useAuth();
  return useQuery({
    queryKey: ["jobs"],
    queryFn: () => unwrap(api.GET("/jobs")),
    enabled: !!session,
    // Mientras haya algo procesándose, refresca; si no, no gasta peticiones.
    refetchInterval: (q) => (q.state.data?.some((j) => ACTIVE.has(j.status)) ? 4000 : false),
  });
}

/** Hay algo generándose en el proyecto: el propio vídeo, un clip editado o más clips. */
export function jobIsBusy(job: Job): boolean {
  return (
    ACTIVE.has(job.status) ||
    job.clips.some((c) => c.status === "rendering") ||
    (!!job.more_clips_task && ACTIVE.has(job.more_clips_task.status))
  );
}

export function useJob(jobId: string) {
  const api = useApi();
  const qc = useQueryClient();
  const { session } = useAuth();
  return useQuery({
    queryKey: ["job", jobId],
    queryFn: async () => {
      const job = await unwrap(api.GET("/jobs/{job_id}", { params: { path: { job_id: jobId } } }));
      if (!ACTIVE.has(job.status)) {
        qc.invalidateQueries({ queryKey: ["jobs"] });
        qc.invalidateQueries({ queryKey: ["me"] });
      }
      return job;
    },
    enabled: !!session && !!jobId,
    refetchInterval: (q) => (q.state.data && !jobIsBusy(q.state.data) ? false : 2000),
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 3,
  });
}

export function useDeleteJob() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => unwrap(api.DELETE("/jobs/{job_id}", { params: { path: { job_id: jobId } } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

export type CreateProjectInput = {
  file: File;
  maxClips: number;
  language: string;
  options: JobOptions;
  /** Tramo a recortar en el servidor (si no se pudo recortar en el navegador). */
  trim?: { start: number; end: number } | null;
  onUploadProgress: (progress: UploadProgress) => void;
  onPhase: (phase: "uploading" | "checking" | "starting") => void;
  signal?: AbortSignal;
};

/** Flujo completo: subir por partes (reanudable) → validar vídeo → crear job. */
export function useCreateProject() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreateProjectInput): Promise<Job> => {
      input.onPhase("uploading");
      const uploadId = await uploadFile(
        api,
        input.file,
        (p) => {
          input.onUploadProgress(p);
          if (p.sentBytes >= p.totalBytes) input.onPhase("checking");
        },
        input.signal,
      );
      input.onPhase("starting");
      return unwrap(
        api.POST("/jobs", {
          body: {
            upload_id: uploadId,
            max_clips: input.maxClips,
            language: input.language,
            ...input.options,
            ...(input.trim ? { trim_start: input.trim.start, trim_end: input.trim.end } : {}),
          },
        }),
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["me"] });
    },
  });
}

/** Elimina la cuenta y todos sus datos. Tras el éxito, quien llama cierra la sesión. */
export function useDeleteAccount() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.DELETE("/me")),
    onSuccess: () => qc.clear(), // que ninguna consulta pendiente vuelva a pedir datos de la cuenta borrada
  });
}

// --------------------------------------------------------------------------- opciones y preferencias

export function useClipOptions() {
  const api = useApi();
  return useQuery({ queryKey: ["options"], queryFn: () => unwrap(api.GET("/options")), staleTime: 60 * 60_000 });
}

export function usePreferences() {
  const api = useApi();
  const { session } = useAuth();
  return useQuery({
    queryKey: ["preferences"],
    queryFn: () => unwrap(api.GET("/me/preferences")),
    enabled: !!session,
  });
}

export function useSavePreferences() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { branding: BrandingPrefs }) => unwrap(api.PUT("/me/preferences", { body })),
    onSuccess: (data) => qc.setQueryData(["preferences"], data),
  });
}

/** Estilos de subtítulos del usuario: los de serie (con sus cambios) y los propios. */
export function useStyles() {
  const api = useApi();
  const { session } = useAuth();
  return useQuery({
    queryKey: ["styles"],
    queryFn: () => unwrap(api.GET("/me/styles")),
    enabled: !!session,
  });
}

export function useStyleActions() {
  const api = useApi();
  const qc = useQueryClient();
  const done = (data: UserStyles) => {
    qc.setQueryData(["styles"], data);
    qc.invalidateQueries({ queryKey: ["preferences"] });
  };
  return {
    create: useMutation({
      mutationFn: (body: { name: string; style: CaptionStyle }) => unwrap(api.POST("/me/styles", { body })),
      onSuccess: done,
    }),
    update: useMutation({
      mutationFn: ({ id, ...body }: { id: string; name?: string; style: CaptionStyle }) =>
        unwrap(api.PUT("/me/styles/{style_id}", { params: { path: { style_id: id } }, body })),
      onSuccess: done,
    }),
    remove: useMutation({
      mutationFn: (id: string) => unwrap(api.DELETE("/me/styles/{style_id}", { params: { path: { style_id: id } } })),
      onSuccess: done,
    }),
    setDefault: useMutation({
      mutationFn: (id: string) => unwrap(api.PUT("/me/default-style", { body: { id } })),
      onSuccess: done,
    }),
  };
}

export function useLogo() {
  const api = useApi();
  const qc = useQueryClient();
  const upload = useMutation({
    mutationFn: (file: File) =>
      unwrap(
        api.PUT("/me/logo", {
          body: file as unknown as string,
          bodySerializer: (b: unknown) => b as BodyInit,
          headers: { "Content-Type": file.type || "image/png" },
        }),
      ),
    onSuccess: (data) => qc.setQueryData(["preferences"], data),
  });
  const remove = useMutation({
    mutationFn: () => unwrap(api.DELETE("/me/logo")),
    onSuccess: (data) => qc.setQueryData(["preferences"], data),
  });
  return { upload, remove };
}

// --------------------------------------------------------------------------- clips

function useJobUpdater() {
  const qc = useQueryClient();
  return (jobId: string, clip: Clip) =>
    qc.setQueryData<Job>(["job", jobId], (job) =>
      job ? { ...job, clips: job.clips.map((c) => (c.id === clip.id ? clip : c)) } : job,
    );
}

export function useUpdateClip(jobId: string) {
  const api = useApi();
  const update = useJobUpdater();
  return useMutation({
    mutationFn: (v: { clipId: string; title?: string; description?: string; hashtags?: string[] }) =>
      unwrap(
        api.PATCH("/clips/{clip_id}", {
          params: { path: { clip_id: v.clipId } },
          body: { title: v.title, description: v.description, hashtags: v.hashtags },
        }),
      ),
    onSuccess: (clip) => update(jobId, clip),
  });
}

export function useRateClip(jobId: string) {
  const api = useApi();
  const update = useJobUpdater();
  return useMutation({
    mutationFn: (v: { clipId: string; value: -1 | 0 | 1 }) =>
      unwrap(api.PUT("/clips/{clip_id}/rating", { params: { path: { clip_id: v.clipId } }, body: { value: v.value } })),
    onSuccess: (clip) => update(jobId, clip),
  });
}

export function useEditor(clipId: string) {
  const api = useApi();
  const { session } = useAuth();
  return useQuery({
    queryKey: ["editor", clipId],
    queryFn: () => unwrap(api.GET("/clips/{clip_id}/editor", { params: { path: { clip_id: clipId } } })),
    enabled: !!session && !!clipId,
    refetchInterval: (q) => (q.state.data?.clip.status === "rendering" ? 2500 : false),
    refetchOnWindowFocus: false, // no pisar las ediciones sin guardar
  });
}

export type RenderInput = {
  start: number;
  end: number;
  word_edits: Record<string, string>;
  caption_style: CaptionStyle | null;
};

export function useRenderClip(jobId: string, clipId: string) {
  const api = useApi();
  const qc = useQueryClient();
  const update = useJobUpdater();
  return useMutation({
    mutationFn: (body: RenderInput) =>
      unwrap(api.POST("/clips/{clip_id}/render", { params: { path: { clip_id: clipId } }, body })),
    onSuccess: (clip) => {
      update(jobId, clip);
      qc.invalidateQueries({ queryKey: ["editor", clipId] });
      qc.invalidateQueries({ queryKey: ["job", jobId] });
    },
  });
}

/** Descarga los subtítulos (la petición lleva la sesión, así que no vale un enlace normal). */
export function useDownloadCaptions() {
  const api = useApi();
  return useMutation({
    mutationFn: async (v: { clipId: string; format: "srt" | "vtt"; filename: string }) => {
      const { data, response } = await api.GET("/clips/{clip_id}/captions", {
        params: { path: { clip_id: v.clipId }, query: { format: v.format } },
        parseAs: "blob",
      });
      if (!response.ok || !data) {
        throw new ApiError("captions", dictionary().errors.captions, response.status);
      }
      saveBlob(data as Blob, v.filename);
    },
  });
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

// --------------------------------------------------------------------------- proyecto

export function useMoreClips(jobId: string) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { count: number; topic: string }) =>
      unwrap(api.POST("/jobs/{job_id}/more", { params: { path: { job_id: jobId } }, body })),
    onSuccess: (job) => qc.setQueryData(["job", jobId], job),
  });
}

/** Pide un enlace temporal y deja que el navegador descargue el ZIP directamente (sin cargarlo en memoria). */
export function useDownloadAll(jobId: string) {
  const api = useApi();
  return useMutation({
    mutationFn: async () => {
      const { url } = await unwrap(api.POST("/jobs/{job_id}/archive", { params: { path: { job_id: jobId } } }));
      window.location.assign(url);
    },
  });
}

/**
 * Mantiene alineados el idioma de la web y el de la cuenta (que decide el idioma de los emails).
 * Si el usuario nunca eligió idioma en este navegador, se adopta el de su cuenta; si la cuenta no tiene
 * ninguno (usuario nuevo), se guarda el del navegador.
 */
export function useLocaleSync() {
  const api = useApi();
  const qc = useQueryClient();
  const { data: me } = useMe();
  const { locale, setLocale } = useI18n();
  useEffect(() => {
    if (!me || me.locale === locale) return;
    // La cuenta ya tiene idioma y este navegador no ha elegido ninguno: se usa el de la cuenta.
    if (me.locale && !getStoredLocale()) {
      setLocale(me.locale);
      return;
    }
    api.PUT("/me/locale", { body: { locale } }).then(() => {
      qc.setQueryData(["me"], { ...me, locale });
    });
  }, [api, qc, me, locale, setLocale]);
}
