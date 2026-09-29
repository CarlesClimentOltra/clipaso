"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeftIcon, Loader2Icon, SparklesIcon } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import type { ClipFormat } from "@/components/caption-preview";
import { slug } from "@/components/clip-card";
import { ClipDownloads } from "@/components/clip-downloads";
import { CLIP_ASPECT, ClipPlayer } from "@/components/clip-player";
import { CoverEditor } from "@/components/editor/cover-editor";
import { EditorPreview } from "@/components/editor/editor-preview";
import { TrimTimeline } from "@/components/editor/trim-timeline";
import { WordEditor } from "@/components/editor/word-editor";
import { StylePicker } from "@/components/style-picker";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, type CaptionStyle, type Editor } from "@/lib/api/client";
import { useEditor, useRenderClip, useUpdateClip } from "@/lib/api/hooks";
import type { TimedWord } from "@/lib/captions";
import { useI18n } from "@/lib/i18n";

function sameEdits(a: Record<string, string>, b: Record<string, string>) {
  const ka = Object.keys(a);
  return ka.length === Object.keys(b).length && ka.every((k) => a[k] === b[k]);
}

function TextsForm({ data, jobId }: { data: Editor; jobId: string }) {
  const update = useUpdateClip(jobId);
  const { t } = useI18n();
  const [title, setTitle] = useState(data.clip.title);
  const [description, setDescription] = useState(data.clip.description);
  const [hashtags, setHashtags] = useState(data.clip.hashtags.map((t) => `#${t}`).join(" "));

  async function save() {
    try {
      await update.mutateAsync({
        clipId: data.clip.id,
        title,
        description,
        hashtags: hashtags.split(/[\s,]+/).filter(Boolean),
      });
      toast.success(t.clip.saved);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : t.clip.saveError);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs text-muted-foreground">{t.editor.textsNote}</p>
      <div className="flex flex-col gap-2">
        <Label htmlFor="ed-title">{t.clip.title}</Label>
        <Input id="ed-title" maxLength={255} value={title} onChange={(e) => setTitle(e.target.value)} />
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="ed-desc">{t.editor.publishDescription}</Label>
        <Textarea id="ed-desc" rows={4} maxLength={2000} value={description}
                  onChange={(e) => setDescription(e.target.value)} />
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="ed-tags">{t.clip.hashtags}</Label>
        <Input id="ed-tags" value={hashtags} placeholder="#viral #podcast" onChange={(e) => setHashtags(e.target.value)} />
      </div>
      <Button type="button" variant="outline" className="self-start" onClick={save} disabled={update.isPending}>
        {update.isPending ? t.common.saving : t.editor.saveTexts}
      </Button>
    </div>
  );
}

function EditorForm({ data, jobId }: { data: Editor; jobId: string }) {
  const router = useRouter();
  const render = useRenderClip(jobId, data.clip.id);
  const { t } = useI18n();
  const e = t.editor;
  // Palabras corregidas ({clave: texto}) y cortes de línea elegidos ({"br:clave": "split" | "join"}).
  const initialEdits = useMemo(
    () => ({
      ...Object.fromEntries(data.words.filter((w) => w.text !== w.original).map((w) => [w.key, w.text])),
      ...Object.fromEntries(data.words.filter((w) => w.brk).map((w) => [`br:${w.key}`, w.brk as string])),
    }),
    [data.words],
  );
  const [start, setStart] = useState(data.clip.start);
  const [end, setEnd] = useState(data.clip.end);
  const [edits, setEdits] = useState<Record<string, string>>(initialEdits);
  const [style, setStyle] = useState<CaptionStyle>(data.caption_style);
  const format = data.format as ClipFormat;
  const rendering = data.clip.status === "rendering";
  const locked = rendering || !data.can_render || render.isPending;

  const timed: TimedWord[] = useMemo(
    () =>
      data.words.map((w) => ({
        key: w.key,
        start: w.start,
        end: w.end,
        text: edits[w.key] ?? w.original,
        brk: (edits[`br:${w.key}`] as "split" | "join" | undefined) ?? null,
      })),
    [data.words, edits],
  );
  const inRange = data.words.filter((w) => w.start >= start - 0.01 && w.end <= end + 0.01);
  const dirty =
    Math.abs(start - data.clip.start) > 0.05 ||
    Math.abs(end - data.clip.end) > 0.05 ||
    !sameEdits(edits, initialEdits) ||
    JSON.stringify(style) !== JSON.stringify(data.caption_style);

  async function save() {
    try {
      await render.mutateAsync({ start, end, word_edits: edits, caption_style: style });
      toast.success(e.started);
      router.push(`/projects/${jobId}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : e.renderError);
    }
  }

  function discard() {
    setStart(data.clip.start);
    setEnd(data.clip.end);
    setEdits(initialEdits);
    setStyle(data.caption_style);
  }

  return (
    <div className="grid gap-8 pb-24 lg:grid-cols-[minmax(0,380px)_1fr]">
      <div className="lg:sticky lg:top-20 lg:self-start">
        {data.preview_url ? (
          <EditorPreview src={data.preview_url} start={start} end={end} words={timed.filter((w) => w.text)}
                         style={style} format={format} />
        ) : (
          <div className="flex flex-col gap-2">
            <ClipPlayer src={data.clip.video_url} poster={data.clip.thumbnail_url ?? undefined} title={data.clip.title}
                        rank={data.clip.rank} aspect={CLIP_ASPECT[format]} />
            <p className="text-center text-xs text-muted-foreground">
              {e.currentVersion}
            </p>
          </div>
        )}
      </div>

      <div className="flex min-w-0 flex-col gap-6">
        {rendering && (
          <Alert>
            <Loader2Icon className="animate-spin" />
            <AlertTitle>{e.renderingTitle}</AlertTitle>
            <AlertDescription>{e.renderingText}</AlertDescription>
          </Alert>
        )}
        {!data.can_render && (
          <Alert>
            <AlertTitle>{e.cannotTitle}</AlertTitle>
            <AlertDescription>
              {e.cannotText}
            </AlertDescription>
          </Alert>
        )}
        {data.clip.status === "failed" && data.clip.render_error && (
          <Alert variant="destructive">
            <AlertDescription>{data.clip.render_error}</AlertDescription>
          </Alert>
        )}

        <Tabs defaultValue={data.can_render ? "trim" : "texts"}>
          <TabsList>
            <TabsTrigger value="trim" disabled={!data.can_render}>{e.tabs.trim}</TabsTrigger>
            <TabsTrigger value="words" disabled={!data.can_render}>{e.tabs.words}</TabsTrigger>
            <TabsTrigger value="style" disabled={!data.can_render}>{e.tabs.style}</TabsTrigger>
            <TabsTrigger value="cover" disabled={!data.clip.cover}>{e.tabs.cover}</TabsTrigger>
            <TabsTrigger value="texts">{e.tabs.texts}</TabsTrigger>
          </TabsList>
          <Card className="mt-2">
            <CardContent>
              <TabsContent value="trim">
                <TrimTimeline
                  min={data.window_start}
                  max={data.window_end}
                  start={start}
                  end={end}
                  words={timed}
                  disabled={locked}
                  previewUrl={data.preview_url}
                  energy={data.energy}
                  energyStep={data.energy_step}
                  onChange={(s, e) => {
                    setStart(s);
                    setEnd(e);
                  }}
                />
              </TabsContent>
              <TabsContent value="words">
                <WordEditor words={inRange} edits={edits} onChange={setEdits} maxWords={style.max_words}
                            disabled={locked} />
              </TabsContent>
              <TabsContent value="style">
                <StylePicker value={style} onChange={setStyle} format={format} disabled={locked} />
              </TabsContent>
              <TabsContent value="cover">
                {data.clip.cover && (
                  <CoverEditor clip={data.clip} jobId={jobId} previewUrl={data.preview_url}
                               canChangeFrame={data.can_render} />
                )}
              </TabsContent>
              <TabsContent value="texts">
                <TextsForm data={data} jobId={jobId} />
              </TabsContent>
            </CardContent>
          </Card>
        </Tabs>
      </div>

      {data.can_render && (
        <div className="fixed inset-x-0 bottom-0 z-20 border-t bg-background/90 backdrop-blur">
          <div className="mx-auto flex w-full max-w-6xl items-center justify-end gap-3 px-4 py-3">
            {dirty && <span className="mr-auto text-sm text-muted-foreground">{e.unsaved}</span>}
            <Button type="button" variant="ghost" onClick={discard} disabled={!dirty || locked}>
              {e.discard}
            </Button>
            <Button type="button" onClick={save} disabled={!dirty || locked}>
              {render.isPending ? <Loader2Icon className="animate-spin" /> : <SparklesIcon />}
              {e.generate}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ClipEditorPage() {
  const { id, clipId } = useParams<{ id: string; clipId: string }>();
  const { data, error, isPending } = useEditor(clipId);
  const { t } = useI18n();

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link href={`/projects/${id}`} className={buttonVariants({ variant: "ghost", size: "sm", className: "self-start" })}>
          <ArrowLeftIcon /> {t.editor.back}
        </Link>
        {data && (
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div className="min-w-0">
              <h1 className="truncate text-2xl font-semibold tracking-tight">{t.editor.title(data.clip.rank)}</h1>
              <p className="truncate text-sm text-muted-foreground">{data.project_title}</p>
            </div>
            {data.clip.status !== "rendering" && (
              <ClipDownloads
                key={data.clip.version}
                clipId={data.clip.id}
                downloadUrl={data.clip.download_url}
                cover={data.clip.cover}
                filenameBase={`${slug(data.project_title)}-${String(data.clip.rank).padStart(2, "0")}-${slug(data.clip.title)}`}
                className="w-44"
              />
            )}
          </div>
        )}
      </div>
      {isPending ? (
        <div className="grid gap-8 lg:grid-cols-[380px_1fr]">
          <Skeleton className="aspect-[9/16] w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      ) : error || !data ? (
        <Alert variant="destructive">
          <AlertTitle>{t.editor.openError}</AlertTitle>
          <AlertDescription>{error instanceof ApiError ? error.message : t.common.loadingError}</AlertDescription>
        </Alert>
      ) : (
        <EditorForm key={`${data.clip.id}-${data.clip.version}-${data.clip.status}`} data={data} jobId={id} />
      )}
    </div>
  );
}
