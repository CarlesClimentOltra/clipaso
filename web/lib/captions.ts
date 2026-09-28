// Agrupa palabras en bloques de subtítulo igual que el motor (adapters/exporters/subtitles.py:
// chunk_words), para que la vista previa del editor muestre lo mismo que tendrá el clip.

/** `brk`: corte elegido por el usuario tras la palabra ("split" nueva línea, "join" seguir en la misma). */
export type TimedWord = { key: string; start: number; end: number; text: string; brk?: "split" | "join" | null };

const TRIM = /^[,.;:…"'«»“”]+|[,.;:…"'«»“”]+$/g;

/** `maxWords`: palabras por línea del estilo; el tiempo máximo por bloque crece con ellas, como en el motor. */
export function chunkWords(words: TimedWord[], maxWords = 3): TimedWord[][] {
  const maxSeconds = Math.max(1.6, 0.55 * maxWords);
  const chunks: TimedWord[][] = [];
  let current: TimedWord[] = [];
  for (const w of words) {
    const last = current[current.length - 1];
    const cut = last?.brk
      ? last.brk === "split"
      : !!last &&
        (current.length >= maxWords ||
          w.end - current[0].start > maxSeconds ||
          /[.?!,]$/.test(last.text.trim()) ||
          w.start - last.end > 0.6);
    if (cut) {
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
