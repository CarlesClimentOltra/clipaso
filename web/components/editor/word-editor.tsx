"use client";

import { CornerDownLeftIcon, LinkIcon, ReplaceIcon, SearchIcon, Undo2Icon, UnlinkIcon } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { EditorWord } from "@/lib/api/client";
import { chunkWords, formatTime, type TimedWord } from "@/lib/captions";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type Brk = "split" | "join";
const brKey = (key: string) => `br:${key}`;

// Puntuación que rodea a una palabra («¿Por», «veces?»): se conserva al reemplazar.
const EDGES = /^([¿¡"'«“(]*)(.*?)([.,;:!?…"'»”)]*)$/u;

/** Palabra completa sin puntuación, para buscar sin distinguir mayúsculas ni tildes de más. */
function core(text: string) {
  return (EDGES.exec(text.trim())?.[2] ?? text).toLowerCase();
}

/**
 * Corrección de subtítulos: las líneas tal como saldrán en pantalla. Se puede cambiar el texto de cada
 * palabra (su tiempo no cambia; vacía, se quita de los subtítulos pero no del audio), cortar una línea
 * donde quieras, unirla con la siguiente y buscar y reemplazar en todo el clip.
 */
export function WordEditor({
  words,
  edits,
  onChange,
  maxWords,
  disabled,
}: {
  words: EditorWord[];
  edits: Record<string, string>;
  onChange: (edits: Record<string, string>) => void;
  maxWords: number;
  disabled?: boolean;
}) {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [search, setSearch] = useState("");
  const [replacement, setReplacement] = useState("");
  const { t } = useI18n();
  const tw = t.editor.words;
  const textOf = (w: EditorWord) => edits[w.key] ?? w.original;
  const brkOf = (w: EditorWord) => (edits[brKey(w.key)] as Brk | undefined) ?? null;
  const changed = Object.keys(edits).length;
  const hasBreaks = Object.keys(edits).some((k) => k.startsWith("br:"));

  // Filas = bloques de subtítulo (igual que el motor); las palabras quitadas se quedan en su fila, tachadas.
  const rows = useMemo(() => {
    const visible: TimedWord[] = words
      .filter((w) => (edits[w.key] ?? w.original).trim())
      .map((w) => ({ key: w.key, start: w.start, end: w.end, text: edits[w.key] ?? w.original,
                     brk: (edits[brKey(w.key)] as Brk | undefined) ?? null }));
    const rowOf = new Map<string, number>();
    chunkWords(visible, maxWords).forEach((chunk, i) => chunk.forEach((w) => rowOf.set(w.key, i)));
    const out: EditorWord[][] = [];
    let current = 0;
    for (const w of words) {
      current = rowOf.get(w.key) ?? current;
      (out[current] ??= []).push(w);
    }
    return out.filter(Boolean);
  }, [words, edits, maxWords]);

  // Se buscan palabras completas: «que» no toca «quedó».
  const query = search.trim().toLowerCase();
  const matches = query ? words.filter((w) => core(textOf(w)) === query) : [];

  function setWord(w: EditorWord, value: string) {
    const next = { ...edits };
    if (value === w.original) delete next[w.key];
    else next[w.key] = value;
    onChange(next);
  }

  function setBreak(w: EditorWord, brk: Brk | null) {
    const next = { ...edits };
    if (brk) next[brKey(w.key)] = brk;
    else delete next[brKey(w.key)];
    onChange(next);
  }

  function commit(w: EditorWord) {
    setWord(w, draft.trim());
    setEditing(null);
  }

  function replaceAll() {
    const next = { ...edits };
    for (const w of matches) {
      const [, before = "", , after = ""] = EDGES.exec(textOf(w).trim()) ?? [];
      const value = `${before}${replacement.trim()}${after}`.trim();
      if (value === w.original) delete next[w.key];
      else next[w.key] = value;
    }
    onChange(next);
  }

  function resetBreaks() {
    onChange(Object.fromEntries(Object.entries(edits).filter(([k]) => !k.startsWith("br:"))));
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs text-muted-foreground">{tw.hint}</p>

      <div className="flex flex-wrap items-center gap-2 rounded-xl bg-muted/50 p-2">
        <div className="relative min-w-40 flex-1">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={tw.search}
                 aria-label={tw.search} className="h-8 bg-background pl-8" disabled={disabled} />
        </div>
        <Input value={replacement} onChange={(e) => setReplacement(e.target.value)} placeholder={tw.replaceWith}
               aria-label={tw.replaceWith} className="h-8 min-w-32 flex-1 bg-background" disabled={disabled} />
        <Button type="button" size="sm" variant="secondary" onClick={replaceAll}
                disabled={disabled || matches.length === 0}>
          <ReplaceIcon /> {tw.replaceAll(matches.length)}
        </Button>
        {query && matches.length === 0 && <span className="text-xs text-muted-foreground">{tw.noMatches}</span>}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs text-muted-foreground">{tw.lines(rows.length)}</span>
        <div className="flex gap-1">
          {hasBreaks && (
            <Button type="button" variant="ghost" size="sm" onClick={resetBreaks} disabled={disabled}>
              <UnlinkIcon /> {tw.resetBreaks}
            </Button>
          )}
          {changed > 0 && (
            <Button type="button" variant="ghost" size="sm" onClick={() => onChange({})} disabled={disabled}>
              <Undo2Icon /> {tw.undo(changed)}
            </Button>
          )}
        </div>
      </div>

      {words.length === 0 ? (
        <p className="text-sm text-muted-foreground">{tw.none}</p>
      ) : (
        <ol className="flex max-h-[26rem] flex-col gap-1 overflow-y-auto rounded-xl border p-2">
          {rows.map((row, ri) => {
            const lastVisible = [...row].reverse().find((w) => textOf(w).trim());
            const userSplit = lastVisible && brkOf(lastVisible) === "split";
            return (
              <li key={row[0].key}
                  className="group flex items-center gap-2 rounded-lg px-2 py-1 hover:bg-muted/50 focus-within:bg-muted/50">
                <span className="w-10 shrink-0 text-[11px] text-muted-foreground tabular-nums">
                  {formatTime(row[0].start)}
                </span>
                <div className="flex min-w-0 flex-1 flex-wrap items-center gap-0.5">
                  {row.map((w, wi) => {
                    const text = textOf(w);
                    const edited = w.key in edits;
                    const hit = query && core(text) === query;
                    const node = editing === w.key ? (
                      <input
                        key={w.key}
                        autoFocus
                        value={draft}
                        maxLength={60}
                        aria-label={tw.fix(w.original)}
                        size={Math.max(3, draft.length + 1)}
                        onChange={(e) => setDraft(e.target.value)}
                        onBlur={() => commit(w)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") commit(w);
                          if (e.key === "Escape") setEditing(null);
                        }}
                        className="rounded-md border border-primary bg-background px-1.5 py-0.5 text-sm ring-3 ring-ring/30 outline-none"
                      />
                    ) : (
                      <button
                        key={w.key}
                        type="button"
                        disabled={disabled}
                        title={edited ? `${tw.original(w.original)} · ${formatTime(w.start, true)}` : formatTime(w.start, true)}
                        onClick={() => {
                          setEditing(w.key);
                          setDraft(text);
                        }}
                        className={cn(
                          "rounded-md px-1 py-0.5 text-sm hover:bg-background",
                          edited && text && "bg-primary/10 text-brand-ink underline decoration-dotted underline-offset-4",
                          edited && !text && "text-muted-foreground line-through",
                          hit && "bg-amber-200/70 dark:bg-amber-500/30",
                        )}
                      >
                        {text || w.original}
                      </button>
                    );
                    const canSplitAfter = wi < row.length - 1 && text.trim();
                    return (
                      <span key={w.key} className="flex items-center">
                        {node}
                        {canSplitAfter && (
                          <button
                            type="button"
                            disabled={disabled}
                            onClick={() => setBreak(w, "split")}
                            aria-label={tw.splitAfter(text)}
                            title={tw.splitHere}
                            className="-mx-0.5 flex w-1.5 justify-center overflow-hidden rounded text-muted-foreground opacity-0 transition-all group-hover:w-4 group-hover:opacity-60 hover:text-brand-ink hover:opacity-100 focus-visible:w-4 focus-visible:opacity-100"
                          >
                            <CornerDownLeftIcon className="size-3" />
                          </button>
                        )}
                      </span>
                    );
                  })}
                </div>
                {lastVisible && ri < rows.length - 1 && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-xs"
                    disabled={disabled}
                    onClick={() => setBreak(lastVisible, userSplit ? null : "join")}
                    aria-label={userSplit ? tw.removeSplit : tw.joinNext}
                    title={userSplit ? tw.removeSplit : tw.joinNext}
                    className="shrink-0 opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
                  >
                    {userSplit ? <UnlinkIcon /> : <LinkIcon />}
                  </Button>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
