"use client";

import { CheckIcon, ImageIcon, RotateCcwIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAdminMessages, useSetMessageStatus } from "@/lib/api/hooks";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

/** Mensajes del formulario de contacto (panel de desarrollo). Se responden desde el correo. */
export function AdminMessages() {
  const { t, formatDate } = useI18n();
  const { data: messages } = useAdminMessages(true);
  const setStatus = useSetMessageStatus();
  const pending = messages?.filter((m) => m.status === "new").length ?? 0;

  return (
    <section className="flex flex-col gap-3">
      <h2 className="flex items-center gap-2 text-lg font-semibold">
        Mensajes de contacto {pending > 0 && <Badge>{pending} sin resolver</Badge>}
      </h2>
      {!messages?.length ? (
        <p className="text-sm text-muted-foreground">Todavía no hay mensajes.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {messages.map((m) => (
            <li key={m.id} className={cn("flex flex-col gap-2 rounded-2xl border bg-card p-4", m.status === "resolved" && "opacity-60")}>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <Badge variant={m.kind === "bug" ? "destructive" : "secondary"}>
                  {t.contact.kinds[m.kind as keyof typeof t.contact.kinds] ?? m.kind}
                </Badge>
                <a href={`mailto:${m.email}`} className="font-medium underline-offset-4 hover:underline">{m.email}</a>
                <span className="text-muted-foreground">{m.has_account ? "con cuenta" : "sin cuenta"}</span>
                <span className="ml-auto text-muted-foreground">
                  {formatDate(m.created_at, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
                </span>
              </div>
              <p className="text-sm whitespace-pre-wrap">{m.message}</p>
              {Object.keys(m.context).length > 0 && (
                <p className="text-xs break-all text-muted-foreground">
                  {Object.entries(m.context).map(([k, v]) => `${k}: ${v}`).join(" · ")}
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                {m.attachment_url && (
                  <a href={m.attachment_url} target="_blank" rel="noopener" className="inline-flex items-center gap-1 text-sm text-brand-ink underline-offset-4 hover:underline">
                    <ImageIcon className="size-4" /> Ver captura
                  </a>
                )}
                <Button size="sm" variant="outline" className="ml-auto" disabled={setStatus.isPending}
                        onClick={() => setStatus.mutate({ id: m.id, status: m.status === "new" ? "resolved" : "new" })}>
                  {m.status === "new" ? <><CheckIcon /> Marcar resuelto</> : <><RotateCcwIcon /> Reabrir</>}
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
