"use client";

import { Undo2Icon } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import type { EditorWord } from "@/lib/api/client";
import { formatTime } from "@/lib/captions";
import { cn } from "@/lib/utils";

/**
 * Corrección de subtítulos palabra a palabra: el tiempo de cada palabra no cambia, solo su texto.
 * Dejar una palabra vacía la quita de los subtítulos (no del audio).
 */
export function WordEditor({
  words,
  edits,
  onChange,
  disabled,
}: {
  words: EditorWord[];
  edits: Record<string, string>;
  onChange: (edits: Record<string, string>) => void;
  disabled?: boolean;
}) {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const changed = Object.keys(edits).length;

  function begin(w: EditorWord) {
    setEditing(w.key);
    setDraft(edits[w.key] ?? w.original);
  }

  function commit(w: EditorWord) {
    const next = { ...edits };
    const value = draft.trim();
    if (value === w.original) delete next[w.key];
    else next[w.key] = value;
    onChange(next);
    setEditing(null);
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          Toca una palabra para corregirla (por ejemplo, un nombre propio). Déjala vacía para quitarla.
        </p>
        {changed > 0 && (
          <Button type="button" variant="ghost" size="sm" onClick={() => onChange({})} disabled={disabled}>
            <Undo2Icon /> Deshacer {changed} {changed === 1 ? "cambio" : "cambios"}
          </Button>
        )}
      </div>
      {words.length === 0 ? (
        <p className="text-sm text-muted-foreground">No hay palabras en este tramo.</p>
      ) : (
        <div className="flex max-h-80 flex-wrap gap-1 overflow-y-auto rounded-lg border p-3">
          {words.map((w) => {
            const edited = w.key in edits;
            const text = edits[w.key] ?? w.original;
            if (editing === w.key) {
              return (
                <input
                  key={w.key}
                  autoFocus
                  value={draft}
                  maxLength={60}
                  aria-label={`Corregir «${w.original}»`}
                  size={Math.max(3, draft.length + 1)}
                  onChange={(e) => setDraft(e.target.value)}
                  onBlur={() => commit(w)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") commit(w);
                    if (e.key === "Escape") setEditing(null);
                  }}
                  className="rounded-md border border-primary bg-background px-1.5 py-0.5 text-sm outline-none ring-3 ring-ring/30"
                />
              );
            }
            return (
              <button
                key={w.key}
                type="button"
                disabled={disabled}
                title={edited ? `Original: ${w.original} · ${formatTime(w.start, true)}` : formatTime(w.start, true)}
                onClick={() => begin(w)}
                className={cn(
                  "rounded-md px-1.5 py-0.5 text-sm hover:bg-muted",
                  edited && text && "bg-primary/10 text-primary underline decoration-dotted underline-offset-4",
                  edited && !text && "text-muted-foreground line-through",
                )}
              >
                {text || w.original}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
