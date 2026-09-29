// Subida por partes, paralela y reanudable, directa del navegador al almacenamiento (R2).
//
// - El fichero se trocea en partes (tamaño decidido por la API) y se suben varias a la vez.
// - Cada parte fallida se reintenta con espera creciente.
// - Qué partes han llegado se guarda en localStorage: si se cierra la pestaña o se corta la
//   conexión, al volver a elegir el mismo fichero se continúa donde se quedó.

import { ApiError, unwrap, type Api } from "@/lib/api/client";
import { dictionary } from "@/lib/i18n";

const CONCURRENCY = 4;
const MAX_RETRIES = 4;
const URL_BATCH = 50;
const STORAGE_PREFIX = "clipaso.upload.";

export type UploadProgress = {
  sentBytes: number;
  totalBytes: number;
  bytesPerSecond: number | null;
  secondsLeft: number | null;
  resumed: boolean;
};

type Saved = { uploadId: string; partSize: number; partCount: number };

function fingerprint(file: File): string {
  return `${STORAGE_PREFIX}${file.name}|${file.size}|${file.lastModified}`;
}

function load(file: File): Saved | null {
  try {
    const raw = localStorage.getItem(fingerprint(file));
    return raw ? (JSON.parse(raw) as Saved) : null;
  } catch {
    return null;
  }
}

function save(file: File, value: Saved | null) {
  try {
    if (value) localStorage.setItem(fingerprint(file), JSON.stringify(value));
    else localStorage.removeItem(fingerprint(file));
  } catch {
    // sin localStorage no se puede reanudar tras cerrar la pestaña, pero la subida funciona
  }
}

function sleep(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const t = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(t);
      reject(new ApiError("aborted", dictionary().errors.aborted, 0));
    });
  });
}

/** PUT de una parte con progreso. Devuelve el ETag que exige el protocolo para completar. */
function putPart(url: string, body: Blob, onProgress: (loaded: number) => void, signal?: AbortSignal) {
  return new Promise<string>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.upload.onprogress = (e) => onProgress(e.loaded);
    xhr.onload = () => {
      const etag = xhr.getResponseHeader("ETag");
      if (xhr.status >= 200 && xhr.status < 300 && etag) resolve(etag);
      else if (xhr.status >= 200 && xhr.status < 300)
        reject(new ApiError("cors_etag", dictionary().errors.cors_etag, xhr.status));
      else reject(new ApiError("part_failed", dictionary().errors.part_failed, xhr.status));
    };
    xhr.onerror = () => reject(new ApiError("network_error", dictionary().errors.upload_network, 0));
    xhr.onabort = () => reject(new ApiError("aborted", dictionary().errors.aborted, 0));
    signal?.addEventListener("abort", () => xhr.abort());
    xhr.send(body);
  });
}

async function startOrResume(api: Api, file: File): Promise<{ saved: Saved; done: Map<number, string>; resumed: boolean }> {
  const previous = load(file);
  if (previous) {
    try {
      const { parts } = await unwrap(
        api.GET("/uploads/{upload_id}/parts", { params: { path: { upload_id: previous.uploadId } } }),
      );
      return { saved: previous, done: new Map(parts.map((p) => [p.part_number, p.etag])), resumed: parts.length > 0 };
    } catch {
      save(file, null); // caducada o ya usada: se empieza de nuevo
    }
  }
  const created = await unwrap(
    api.POST("/uploads", { body: { filename: file.name, size_bytes: file.size, content_type: file.type } }),
  );
  const saved = { uploadId: created.upload_id, partSize: created.part_size, partCount: created.part_count };
  save(file, saved);
  return { saved, done: new Map(), resumed: false };
}

export async function uploadFile(
  api: Api,
  file: File,
  onProgress: (p: UploadProgress) => void,
  signal?: AbortSignal,
): Promise<string> {
  const { saved, done, resumed } = await startOrResume(api, file);
  const { uploadId, partSize, partCount } = saved;
  const sizeOf = (n: number) => Math.min(partSize, file.size - (n - 1) * partSize);

  const inFlight = new Map<number, number>();
  let confirmed = [...done.keys()].reduce((acc, n) => acc + sizeOf(n), 0);
  const startedAt = performance.now();
  const baseline = confirmed; // lo ya subido antes no cuenta para la velocidad
  const report = () => {
    const sent = confirmed + [...inFlight.values()].reduce((a, b) => a + b, 0);
    const elapsed = (performance.now() - startedAt) / 1000;
    const speed = elapsed > 2 ? (sent - baseline) / elapsed : null;
    onProgress({
      sentBytes: sent,
      totalBytes: file.size,
      bytesPerSecond: speed,
      secondsLeft: speed && speed > 0 ? (file.size - sent) / speed : null,
      resumed,
    });
  };
  report();

  const pending = Array.from({ length: partCount }, (_, i) => i + 1).filter((n) => !done.has(n));
  // URLs firmadas por lotes; las peticiones en curso se comparten para no pedir el mismo lote varias veces.
  const urls = new Map<number, Promise<string>>();
  function urlFor(n: number): Promise<string> {
    if (!urls.has(n)) {
      const batch = pending.filter((p) => p >= n && !urls.has(p)).slice(0, URL_BATCH);
      const request = unwrap(
        api.POST("/uploads/{upload_id}/parts", {
          params: { path: { upload_id: uploadId } },
          body: { part_numbers: batch },
        }),
      );
      for (const p of batch) {
        urls.set(
          p,
          request.then((res) => res.urls.find((u) => u.part_number === p)!.url),
        );
      }
      request.catch(() => batch.forEach((p) => urls.delete(p))); // si falla, se reintentará
    }
    return urls.get(n)!;
  }

  async function uploadPart(n: number) {
    const blob = file.slice((n - 1) * partSize, (n - 1) * partSize + sizeOf(n));
    for (let attempt = 0; ; attempt++) {
      try {
        const etag = await putPart(await urlFor(n), blob, (loaded) => {
          inFlight.set(n, loaded);
          report();
        }, signal);
        inFlight.delete(n);
        done.set(n, etag);
        confirmed += sizeOf(n);
        report();
        return;
      } catch (err) {
        inFlight.delete(n);
        if (err instanceof ApiError && (err.code === "aborted" || err.code === "cors_etag")) throw err;
        if (attempt >= MAX_RETRIES) throw err;
        if (err instanceof ApiError && err.status === 403) urls.delete(n); // URL caducada: pedir otra
        await sleep(1000 * 2 ** attempt, signal);
      }
    }
  }

  const queue = [...pending];
  await Promise.all(
    Array.from({ length: Math.min(CONCURRENCY, queue.length) }, async () => {
      for (let n = queue.shift(); n !== undefined; n = queue.shift()) await uploadPart(n);
    }),
  );

  const parts = [...done.entries()].sort((a, b) => a[0] - b[0]).map(([part_number, etag]) => ({ part_number, etag }));
  await unwrap(
    api.POST("/uploads/{upload_id}/complete", { params: { path: { upload_id: uploadId } }, body: { parts } }),
  );
  save(file, null);
  return uploadId;
}

/** Cancela en el servidor una subida pendiente de este fichero (si la hay) y olvida su progreso. */
export async function discardUpload(api: Api, file: File): Promise<void> {
  const previous = load(file);
  save(file, null);
  if (previous) {
    await api.DELETE("/uploads/{upload_id}", { params: { path: { upload_id: previous.uploadId } } }).catch(() => {});
  }
}
