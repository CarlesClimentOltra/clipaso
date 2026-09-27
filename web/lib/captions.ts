// Agrupa palabras en bloques de subtítulo igual que el motor (adapters/exporters/subtitles.py:
// chunk_words), para que la vista previa del editor muestre lo mismo que tendrá el clip.

export type TimedWord = { key: string; start: number; end: number; text: string };

const MAX_WORDS = 3;
const MAX_SECONDS = 1.6;
const TRIM = /^[,.;:…"'«»“”]+|[,.;:…"'«»“”]+$/g;

export function chunkWords(words: TimedWord[]): TimedWord[][] {
  const chunks: TimedWord[][] = [];
  let current: TimedWord[] = [];
  for (const w of words) {
    const last = current[current.length - 1];
    if (
      last &&
      (current.length >= MAX_WORDS ||
        w.end - current[0].start > MAX_SECONDS ||
        /[.?!,]$/.test(last.text.trim()) ||
        w.start - last.end > 0.6)
    ) {
      chunks.push(current);
      current = [];
    }
    current.push(w);
  }
  if (current.length) chunks.push(current);
  return chunks;
}

/** Bloque que se ve en el instante `t` y la palabra resaltada (o null si no hay subtítulo). */
export function captionAt(chunks: TimedWord[][], t: number): { words: string[]; active: number } | null {
  for (let ci = 0; ci < chunks.length; ci++) {
    const chunk = chunks[ci];
    const nextStart = chunks[ci + 1]?.[0].start ?? Infinity;
    const end = Math.min(chunk[chunk.length - 1].end + 0.25, nextStart);
    if (t >= chunk[0].start && t < end) {
      let active = chunk.findIndex((w, i) => t >= w.start && t < (chunk[i + 1]?.start ?? end));
      if (active < 0) active = chunk.length - 1;
      return { words: chunk.map((w) => w.text.trim().replace(TRIM, "")), active };
    }
  }
  return null;
}

export function formatTime(seconds: number, withTenths = false): string {
  const m = Math.floor(seconds / 60);
  const s = seconds - m * 60;
  const whole = Math.floor(s).toString().padStart(2, "0");
  return withTenths ? `${m}:${whole}.${Math.floor((s % 1) * 10)}` : `${m}:${whole}`;
}
