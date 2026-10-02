"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useRef, useState, type FormEvent } from "react";
import { CheckCircle2Icon, ImagePlusIcon, Loader2Icon, SendIcon, XIcon } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api/client";
import { useMe, useSendContact, type ContactKind } from "@/lib/api/hooks";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { legal } from "@/lib/legal";
import { cn } from "@/lib/utils";

const KINDS: ContactKind[] = ["question", "idea", "bug", "billing", "other"];
const MAX_ATTACHMENT = 6 * 1024 * 1024;

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

function ContactForm() {
  const params = useSearchParams();
  const { t, locale } = useI18n();
  const c = t.contact;
  const { session } = useAuth();
  const { data: me } = useMe();
  const send = useSendContact();
  const initialKind = KINDS.includes(params.get("tipo") as ContactKind) ? (params.get("tipo") as ContactKind) : "question";
  const project = params.get("proyecto") ?? "";
  const [kind, setKind] = useState<ContactKind>(initialKind);
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [website, setWebsite] = useState(""); // trampa para bots (invisible)
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const loggedIn = !!session;

  function pick(next: File | undefined) {
    setError(null);
    if (!next) return;
    if (next.size > MAX_ATTACHMENT) {
      setError(c.attachTooBig);
      return;
    }
    setFile(next);
    setPreview(URL.createObjectURL(next));
  }

  function clearFile() {
    setFile(null);
    setPreview(null);
    if (fileRef.current) fileRef.current.value = "";
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    // Contexto para reproducir errores: de dónde viene, navegador, pantalla e idioma.
    const context: Record<string, string> = {
      page: params.get("desde") ?? "/contacto",
      browser: navigator.userAgent,
      screen: `${window.innerWidth}x${window.innerHeight}`,
      language: locale,
    };
    if (project) context.project = project;
    try {
      await send.mutateAsync({
        kind, message, website, context,
        email: loggedIn ? null : email,
        attachment: file ? await readAsDataUrl(file) : null,
      });
      setSent(true);
      setMessage("");
      clearFile();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : c.error);
    }
  }

  if (sent) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-4 py-10 text-center">
          <CheckCircle2Icon className="size-12 text-brand-ink" />
          <h2 className="text-xl font-semibold">{c.sentTitle}</h2>
          <p className="max-w-md text-muted-foreground">{c.sentText}</p>
          <Button variant="outline" onClick={() => setSent(false)}>{c.another}</Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-6">
      <Card>
        <CardContent className="flex flex-col gap-6">
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-sm font-medium">{c.kindLabel}</legend>
            <div className="flex flex-wrap gap-2" role="radiogroup">
              {KINDS.map((k) => (
                <button
                  key={k}
                  type="button"
                  role="radio"
                  aria-checked={kind === k}
                  onClick={() => setKind(k)}
                  className={cn(
                    "rounded-full border px-4 py-1.5 text-sm transition-colors",
                    kind === k ? "border-foreground bg-foreground text-background" : "hover:border-foreground/40",
                  )}
                >
                  {c.kinds[k]}
                </button>
              ))}
            </div>
            {project && <p className="text-xs text-muted-foreground">{c.project(project)}</p>}
          </fieldset>

          <div className="flex flex-col gap-2">
            <Label htmlFor="contact-email">{c.email}</Label>
            {loggedIn ? (
              <>
                <Input id="contact-email" value={me?.email ?? session?.email ?? ""} disabled />
                <p className="text-xs text-muted-foreground">{c.emailAccount}</p>
              </>
            ) : (
              <>
                <Input id="contact-email" type="email" required autoComplete="email" value={email}
                       onChange={(e) => setEmail(e.target.value)} />
                <p className="text-xs text-muted-foreground">{c.emailHint}</p>
              </>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="contact-message">{c.message}</Label>
            <Textarea id="contact-message" required maxLength={5000} rows={7} value={message}
                      placeholder={c.placeholder[kind]} onChange={(e) => setMessage(e.target.value)} />
          </div>

          <div className="flex flex-col gap-2">
            <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
            {preview ? (
              <div className="flex items-center gap-3">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={preview} alt="" className="h-20 w-auto rounded-lg border object-cover" />
                <Button type="button" variant="ghost" size="sm" onClick={clearFile}>
                  <XIcon /> {c.attachRemove}
                </Button>
              </div>
            ) : (
              <Button type="button" variant="outline" className="self-start" onClick={() => fileRef.current?.click()}>
                <ImagePlusIcon /> {c.attach}
              </Button>
            )}
            <p className="text-xs text-muted-foreground">{c.attachHint}</p>
          </div>

          {/* Campo trampa: invisible para las personas, los bots lo rellenan. */}
          <input type="text" name="website" tabIndex={-1} autoComplete="off" aria-hidden="true" value={website}
                 onChange={(e) => setWebsite(e.target.value)} className="absolute -left-[9999px] h-0 w-0 opacity-0" />

          {error && (
            <Alert variant="destructive">
              <AlertTitle>{c.error}</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <Button type="submit" className="self-start" disabled={send.isPending || !message.trim()}>
            {send.isPending ? <Loader2Icon className="animate-spin" /> : <SendIcon />}
            {send.isPending ? c.sending : c.send}
          </Button>
        </CardContent>
      </Card>
      <p className="text-sm text-muted-foreground">
        {c.direct}{" "}
        <a href={`mailto:${legal.owner.email}`} className="font-medium text-brand-ink underline-offset-4 hover:underline">
          {legal.owner.email}
        </a>
      </p>
    </form>
  );
}

export default function ContactPage() {
  const { t } = useI18n();
  const c = t.contact;
  return (
    <div className="flex flex-col gap-6">
      <PageHeader eyebrow={c.eyebrow} title={c.title} description={c.lead} />
      <Suspense>
        <ContactForm />
      </Suspense>
    </div>
  );
}
