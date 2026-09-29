// Fotogramas de un vídeo local, sacados en el navegador (el vídeo no se sube): para las miniaturas.

export type ExtractedFrame = { time: number; image: string }; // image: JPEG en base64

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] ?? "");
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

/**
 * `count` fotogramas repartidos por todo el vídeo (sin los primeros y últimos segundos, que suelen ser
 * negros o de transición), reducidos a `width` px de ancho y en JPEG.
 */
export async function extractFrames(
  file: File,
  count = 20,
  width = 1280,
  onProgress?: (done: number, total: number) => void,
): Promise<ExtractedFrame[]> {
  const url = URL.createObjectURL(file);
  const video = document.createElement("video");
  video.muted = true;
  video.playsInline = true;
  video.preload = "auto";
  video.src = url;
  const once = (event: string, ms: number) =>
    new Promise<boolean>((resolve) => {
      const timer = window.setTimeout(() => resolve(false), ms);
      video.addEventListener(event, () => {
        window.clearTimeout(timer);
        resolve(true);
      }, { once: true });
    });
  try {
    if (!(await once("loadeddata", 30000)) || !video.videoWidth || !Number.isFinite(video.duration)) {
      throw new Error("video");
    }
    const duration = video.duration;
    const margin = Math.min(3, duration * 0.04);
    const scale = Math.min(1, width / video.videoWidth);
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    const ctx = canvas.getContext("2d")!;
    const frames: ExtractedFrame[] = [];
    for (let i = 0; i < count; i++) {
      const time = margin + ((duration - 2 * margin) * (i + 0.5)) / count;
      const seeked = once("seeked", 8000);
      video.currentTime = time;
      if (!(await seeked)) continue;
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.85));
      if (blob) frames.push({ time: Math.round(time * 100) / 100, image: await blobToBase64(blob) });
      onProgress?.(i + 1, count);
    }
    if (!frames.length) throw new Error("frames");
    return frames;
  } finally {
    video.removeAttribute("src");
    video.load();
    URL.revokeObjectURL(url);
  }
}
