"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";

import { ApiError, createApi, unwrap, type Api, type Job } from "@/lib/api/client";
import { useAuth } from "@/lib/auth";

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
    refetchInterval: (q) => (q.state.data && !ACTIVE.has(q.state.data.status) ? false : 2000),
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

/** Sube un fichero directamente al almacenamiento con progreso (fetch no informa del progreso de subida). */
function putWithProgress(
  url: string,
  method: string,
  headers: Record<string, string>,
  file: File,
  onProgress: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method, url);
    Object.entries(headers).forEach(([k, v]) => xhr.setRequestHeader(k, v));
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? resolve()
        : reject(new ApiError("upload_failed", "La subida del vídeo falló. Vuelve a intentarlo.", xhr.status));
    xhr.onerror = () => reject(new ApiError("network_error", "Se perdió la conexión durante la subida.", 0));
    xhr.onabort = () => reject(new ApiError("aborted", "Subida cancelada.", 0));
    signal?.addEventListener("abort", () => xhr.abort());
    xhr.send(file);
  });
}

export type CreateProjectInput = {
  file: File;
  maxClips: number;
  language: string;
  onUploadProgress: (fraction: number) => void;
  onPhase: (phase: "uploading" | "checking" | "starting") => void;
  signal?: AbortSignal;
};

/** Flujo completo: pedir URL de subida → subir → validar vídeo → crear job. */
export function useCreateProject() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreateProjectInput): Promise<Job> => {
      input.onPhase("uploading");
      const created = await unwrap(
        api.POST("/uploads", {
          body: { filename: input.file.name, size_bytes: input.file.size, content_type: input.file.type },
        }),
      );
      await putWithProgress(
        created.target.url,
        created.target.method,
        created.target.headers,
        input.file,
        input.onUploadProgress,
        input.signal,
      );
      input.onPhase("checking");
      await unwrap(
        api.POST("/uploads/{upload_id}/complete", { params: { path: { upload_id: created.upload_id } } }),
      );
      input.onPhase("starting");
      return unwrap(
        api.POST("/jobs", {
          body: { upload_id: created.upload_id, max_clips: input.maxClips, language: input.language },
        }),
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["me"] });
    },
  });
}
