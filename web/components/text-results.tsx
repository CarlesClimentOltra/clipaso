"use client";

import {
  AtSignIcon,
  BookOpenTextIcon,
  CheckIcon,
  CopyIcon,
  DownloadIcon,
  FileTextIcon,
  ListOrderedIcon,
  SearchIcon,
  SparklesIcon,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { slug } from "@/components/clip-card";
import { Button } from "@/components/ui/button";
import { ApiError, type Job } from "@/lib/api/client";
import { saveBlob, useDownloadTranscript } from "@/lib/api/hooks";
import { formatTime } from "@/lib/captions";
import { useI18n } from "@/lib/i18n";

type Results = NonNullable<Job["text_results"]>;

function CopyButton({ text }: { text: string }) {
  const { t } = useI18n();
  const [done, setDone] = useState(false);
  return (
    <Button type="button" variant="outline" size="sm" className="shrink-0" onClick={async () => {
      await navigator.clipboard.writeText(text);
      setDone(true);
      setTimeout(() => setDone(false), 1500);
    }}>
      {done ? <CheckIcon /> : <CopyIcon />} {done ? t.text.copied : t.text.copy}
    </Button>
  );
}

function Section({ icon: Icon, title, meta, copy, children }: {
  icon: typeof FileTextIcon; title: string; meta?: string; copy?: string; children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3 rounded-[1.5rem] border bg-card p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 font-semibold">
          <Icon className="size-4 text-brand-ink" /> {title}
          {meta && <span className="text-xs font-normal text-muted-foreground">· {meta}</span>}
        </h3>
        {copy && <CopyButton text={copy} />}
      </div>
      {children}
    </section>
  );
}

/** `**negrita**` dentro de una línea. */
function inline(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : part);
}

/** Markdown sencillo del artículo (subtítulos, listas, negrita y párrafos), sin librerías ni HTML crudo. */
function Markdown({ source }: { source: string }) {
  const blocks = source.split(/\n{2,}/).map((b) => b.trim()).filter(Boolean);
  return (
    <div className="flex flex-col gap-3">
      {blocks.map((block, i) => {
        const heading = /^(#{1,4})\s+(.*)$/.exec(block);
        if (heading) {
          return <h5 key={i} className="pt-1 text-base font-semibold">{inline(heading[2])}</h5>;
        }
        const lines = block.split("\n");
        if (lines.every((l) => /^\s*([-*•]|\d+\.)\s+/.test(l))) {
          return (
            <ul key={i} className="flex list-disc flex-col gap-1 pl-5">
              {lines.map((l, j) => <li key={j}>{inline(l.replace(/^\s*([-*•]|\d+\.)\s+/, ""))}</li>)}
            </ul>
          );
        }
        return <p key={i}>{inline(block.replace(/\n/g, " "))}</p>;
      })}
    </div>
  );
}

/** Todo en un único Markdown para guardarlo o pegarlo en otra herramienta. */
function asMarkdown(r: Results, title: string, x: ReturnType<typeof useI18n>["t"]["text"]): string {
  return [
    `# ${title}`, `## ${x.summary}`, r.summary, `### ${x.keyPoints}`, r.key_points.map((p) => `- ${p}`).join("\n"),
    ...(r.chapters_text ? [`## ${x.chapters}`, r.chapters_text] : []),
    `## ${x.blog}`, `### ${r.blog_title}`, r.blog_markdown, `## ${x.linkedin}`, r.linkedin,
    `## ${x.thread}`, r.thread.map((p, i) => `${i + 1}/ ${p}`).join("\n\n"),
    `## ${x.seo}`, `**${x.seoTitle}:** ${r.seo_title}`, `**${x.seoDescription}:** ${r.seo_description}`,
    `**${x.seoTags}:** ${r.seo_tags.join(", ")}`,
  ].join("\n\n") + "\n";
}

export function TextResults({ job }: { job: Job }) {
  const { t } = useI18n();
  const x = t.text;
  const r = job.text_results!;
  const transcript = useDownloadTranscript();
  const base = slug(job.title);
  const words = (s: string) => s.split(/\s+/).filter(Boolean).length;

  async function download(format: "txt" | "srt" | "vtt") {
    try {
      await transcript.mutateAsync({ jobId: job.id, format, filename: `${base}-transcripcion.${format}` });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : t.common.genericError);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <section className="flex flex-col gap-4 rounded-[1.5rem] border bg-brand-soft/40 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
        <div>
          <h3 className="flex items-center gap-2 font-semibold"><FileTextIcon className="size-4 text-brand-ink" /> {x.transcript}</h3>
          <p className="text-sm text-muted-foreground">{x.transcriptLead}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {(["txt", "srt", "vtt"] as const).map((f) => (
            <Button key={f} type="button" variant={f === "txt" ? "default" : "outline"} size="sm"
                    disabled={transcript.isPending} onClick={() => download(f)}>
              <DownloadIcon /> {x.download(f.toUpperCase())}
            </Button>
          ))}
          <Button type="button" variant="ghost" size="sm"
                  onClick={() => saveBlob(new Blob([asMarkdown(r, job.title, x)], { type: "text/markdown" }), `${base}-textos.md`)}>
            <DownloadIcon /> {x.downloadAll}
          </Button>
        </div>
      </section>

      <div className="grid gap-5 lg:grid-cols-2">
        <Section icon={SparklesIcon} title={x.summary}
                 copy={`${r.summary}\n\n${r.key_points.map((p) => `• ${p}`).join("\n")}`}>
          <p className="text-sm leading-relaxed">{r.summary}</p>
          {r.key_points.length > 0 && (
            <div>
              <p className="mb-1.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">{x.keyPoints}</p>
              <ul className="flex flex-col gap-1.5 text-sm">
                {r.key_points.map((p) => (
                  <li key={p} className="flex gap-2"><CheckIcon className="mt-0.5 size-4 shrink-0 text-brand-ink" /> {p}</li>
                ))}
              </ul>
            </div>
          )}
        </Section>

        <Section icon={ListOrderedIcon} title={x.chapters} copy={r.chapters_text || undefined}
                 meta={r.chapters.length ? x.chaptersHint : undefined}>
          {r.chapters.length ? (
            <ol className="flex flex-col gap-1 text-sm">
              {r.chapters.map((c) => (
                <li key={c.start} className="flex gap-3">
                  <span className="w-12 shrink-0 font-mono text-brand-ink tabular-nums">{formatTime(c.start)}</span>
                  {c.title}
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-sm text-muted-foreground">{x.noChapters}</p>
          )}
        </Section>
      </div>

      <Section icon={BookOpenTextIcon} title={x.blog} meta={x.words(words(r.blog_markdown))}
               copy={`# ${r.blog_title}\n\n${r.blog_markdown}`}>
        <h4 className="text-lg font-semibold">{r.blog_title}</h4>
        <div className="max-h-128 overflow-y-auto rounded-xl bg-muted/40 p-4 text-sm leading-relaxed sm:p-5">
          <Markdown source={r.blog_markdown} />
        </div>
      </Section>

      <div className="grid gap-5 lg:grid-cols-2">
        <Section icon={AtSignIcon} title={x.linkedin} meta={x.words(words(r.linkedin))} copy={r.linkedin}>
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{r.linkedin}</p>
        </Section>
        <Section icon={AtSignIcon} title={x.thread} meta={x.posts(r.thread.length)}
                 copy={r.thread.map((p, i) => `${i + 1}/ ${p}`).join("\n\n")}>
          <ol className="flex flex-col gap-2 text-sm">
            {r.thread.map((p, i) => (
              <li key={i} className="rounded-xl border bg-background p-3 leading-relaxed">
                <span className="mr-1 font-semibold text-brand-ink">{i + 1}/</span>{p}
              </li>
            ))}
          </ol>
        </Section>
      </div>

      <Section icon={SearchIcon} title={x.seo}
               copy={`${r.seo_title}\n\n${r.seo_description}\n\n${r.seo_tags.join(", ")}`}>
        <dl className="grid gap-3 text-sm sm:grid-cols-[140px_1fr]">
          <dt className="text-muted-foreground">{x.seoTitle}</dt>
          <dd className="font-medium">{r.seo_title}</dd>
          <dt className="text-muted-foreground">{x.seoDescription}</dt>
          <dd>{r.seo_description}</dd>
          <dt className="text-muted-foreground">{x.seoTags}</dt>
          <dd className="flex flex-wrap gap-1.5">
            {r.seo_tags.map((tag) => <span key={tag} className="rounded-full border px-2 py-0.5 text-xs">{tag}</span>)}
          </dd>
        </dl>
      </Section>
    </div>
  );
}
