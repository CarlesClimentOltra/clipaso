// Copia ffmpeg.wasm a public/ffmpeg para servirlo desde nuestro dominio (sin CDN de terceros).
// Se ejecuta tras `npm install` (también en Vercel); public/ffmpeg no se guarda en git.
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(root, "public", "ffmpeg");
const files = [
  ["@ffmpeg/core/dist/esm/ffmpeg-core.js", "ffmpeg-core.js"],
  ["@ffmpeg/core/dist/esm/ffmpeg-core.wasm", "ffmpeg-core.wasm"],
  // El worker de @ffmpeg/ffmpeg se sirve tal cual: así no depende de cómo lo empaquete Next.
  ["@ffmpeg/ffmpeg/dist/esm/worker.js", "worker.js"],
  ["@ffmpeg/ffmpeg/dist/esm/const.js", "const.js"],
  ["@ffmpeg/ffmpeg/dist/esm/errors.js", "errors.js"],
];
mkdirSync(out, { recursive: true });
for (const [from, to] of files) {
  const src = join(root, "node_modules", from);
  if (!existsSync(src)) {
    console.warn(`copy-ffmpeg: falta ${from}`);
    continue;
  }
  copyFileSync(src, join(out, to));
}
console.log("copy-ffmpeg: listo en public/ffmpeg");
