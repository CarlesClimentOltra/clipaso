import type { ReactNode } from "react";

import { Brand } from "@/components/brand";

/** Pantalla sencilla con la marca para 404 y errores inesperados. */
export function StatusPage({ code, title, text, children }: { code: string; title: string; text: string; children: ReactNode }) {
  return (
    <main className="flex min-h-[70vh] flex-1 flex-col items-center justify-center gap-6 px-4 py-16 text-center">
      <Brand />
      <p className="text-6xl font-semibold tracking-tight text-brand-ink">{code}</p>
      <div className="flex max-w-md flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="text-muted-foreground">{text}</p>
      </div>
      <div className="flex flex-wrap justify-center gap-3">{children}</div>
    </main>
  );
}
