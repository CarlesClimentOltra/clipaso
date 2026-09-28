// Recorte del vídeo en el navegador antes de subirlo: solo viaja el tramo elegido.
//
// Usa ffmpeg compilado a WebAssembly (servido desde /ffmpeg, ver scripts/copy-ffmpeg.mjs). El archivo
// se lee por trozos (WORKERFS), sin cargarlo entero en memoria, y el tramo se copia sin recodificar:
// tarda segundos y no pierde calidad. Como no se recodifica, el corte empieza en el fotograma clave
// anterior al inicio elegido (normalmente, menos de 1-2 s antes).

import type { FFmpeg } from "@ffmpeg/ffmpeg";

/** Por encima de este tamaño estimado del tramo, mejor recortar en el servidor (memoria del navegador). */
export const MAX_CLIENT_TRIM_BYTES = 1.5 * 1024 ** 3;

/** Si el recortador no carga en este tiempo (red lenta, bloqueado…), se recorta en el servidor. */
const LOAD_TIMEOUT_MS = 90_000;
const EXEC_TIMEOUT_MS = 5 * 60_000;

let loading: Promise<FFmpeg> | null = null;

async function ffmpeg(): Promise<FFmpeg> {
  loading ??= (async () => {
    const { FFmpeg } = await import("@ffmpeg/ffmpeg");
    const ff = new FFmpeg();
    const base = `${window.location.origin}/ffmpeg`;
    // Si el worker no llega a arrancar, load() no falla nunca: se corta por tiempo.
    let timer: number | undefined;
    const timeout = new Promise<never>((_, reject) => {
      timer = window.setTimeout(() => reject(new Error("ffmpeg no cargó a tiempo")), LOAD_TIMEOUT_MS);
    });
    try {
      await Promise.race([
        ff.load({
          coreURL: `${base}/ffmpeg-core.js`,
          wasmURL: `${base}/ffmpeg-core.wasm`,
          classWorkerURL: `${base}/worker.js`,
        }),
        timeout,
      ]);
    } catch (err) {
      ff.terminate();
      throw err;
    } finally {
      window.clearTimeout(timer);
    }
    return ff;
  })().catch((err) => {
    loading = null; // permite reintentar
    throw err;
  });
  return loading;
}

/** Empieza a descargar ffmpeg en segundo plano (p. ej. al elegir un tramo), para que el recorte sea inmediato. */
export function preloadTrimmer() {
  ffmpeg().catch(() => {});
}

function parseTime(line: string): number | null {
  const m = /time=\s*(\d+):(\d+):(\d+(?:\.\d+)?)/.exec(line);
  return m ? Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3]) : null;
}

/** Devuelve un archivo nuevo con el tramo [start, end] (segundos) del vídeo. */
export async function trimVideo(
  file: File,
  start: number,
  end: number,
  onProgress?: (fraction: number) => void,
): Promise<File> {
  const ff = await ffmpeg();
  const ext = (file.name.match(/\.[^.]+$/)?.[0] ?? ".mp4").toLowerCase();
  const dir = `/in-${Date.now()}`;
  const output = `/tramo${ext}`;
  const duration = end - start;
  const onLog = ({ message }: { message: string }) => {
    const t = parseTime(message);
    if (t != null && onProgress) onProgress(Math.min(1, t / duration));
  };
  ff.on("log", onLog);
  await ff.createDir(dir);
  await ff.mount("WORKERFS" as never, { files: [file] }, dir);
  try {
    const code = await ff.exec([
      "-ss", start.toFixed(3),
      "-i", `${dir}/${file.name}`,
      "-t", duration.toFixed(3),
      "-map", "0:v:0", "-map", "0:a:0?",
      "-c", "copy",
      "-avoid_negative_ts", "make_zero",
      ...(ext === ".mp4" || ext === ".mov" || ext === ".m4v" ? ["-movflags", "+faststart"] : []),
      output,
    ], EXEC_TIMEOUT_MS);
    if (code !== 0) throw new Error(`ffmpeg terminó con código ${code}`);
    const data = await ff.readFile(output);
    if (!(data instanceof Uint8Array) || data.byteLength === 0) throw new Error("recorte vacío");
    onProgress?.(1);
    const stem = file.name.replace(/\.[^.]+$/, "");
    return new File([data as Uint8Array<ArrayBuffer>], `${stem}${ext}`, { type: file.type || "video/mp4" });
  } finally {
    ff.off("log", onLog);
    await ff.deleteFile(output).catch(() => {});
    await ff.unmount(dir).catch(() => {});
    await ff.deleteDir(dir).catch(() => {});
  }
}
