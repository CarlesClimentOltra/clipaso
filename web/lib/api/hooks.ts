"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";

import { ApiError, createApi, unwrap, type Api, type Job } from "@/lib/api/client";
import { uploadFile, type UploadProgress } from "@/lib/api/multipart-upload";
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

export type CreateProjectInput = {
  file: File;
  maxClips: number;
  language: string;
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
        api.POST("/jobs", { body: { upload_id: uploadId, max_clips: input.maxClips, language: input.language } }),
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["me"] });
    },
  });
}
