import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Permite levantar una segunda instancia (p. ej. pruebas automáticas) sin chocar con `npm run dev`.
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
