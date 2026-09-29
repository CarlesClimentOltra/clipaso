import {
  AudioLinesIcon,
  CaptionsIcon,
  ClapperboardIcon,
  ImageIcon,
  RatioIcon,
  ScissorsIcon,
  type LucideIcon,
} from "lucide-react";

/** Modos de «Nuevo proyecto». Cada uno tiene su pantalla en /new/<id>; los textos están en `t.newProject.modes`. */
export const MODES = [
  { id: "clips", icon: ScissorsIcon, usesMinutes: true, isNew: false },
  { id: "subtitle", icon: CaptionsIcon, usesMinutes: true, isNew: false },
  { id: "clean", icon: AudioLinesIcon, usesMinutes: true, isNew: true },
  { id: "reframe", icon: RatioIcon, usesMinutes: true, isNew: true },
  { id: "trailer", icon: ClapperboardIcon, usesMinutes: true, isNew: true },
  { id: "thumbnail", icon: ImageIcon, usesMinutes: false, isNew: true },
] as const satisfies readonly { id: string; icon: LucideIcon; usesMinutes: boolean; isNew: boolean }[];

export type Mode = (typeof MODES)[number]["id"];
/** Modos en los que se sube el vídeo (la miniatura va por otro camino). */
export type VideoMode = Exclude<Mode, "thumbnail">;

export function findMode(id: string | undefined) {
  return MODES.find((m) => m.id === id);
}
