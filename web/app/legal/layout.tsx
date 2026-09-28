import type { ReactNode } from "react";

import { Brand } from "@/components/brand";
import { LegalLanguageNote } from "@/components/legal-language-note";
import { SiteFooter } from "@/components/site-footer";

export default function LegalLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-1 flex-col">
      <header className="mx-auto flex h-16 w-full max-w-3xl items-center px-4">
        <Brand />
      </header>
      <main className="legal mx-auto w-full max-w-3xl flex-1 px-4 pt-6 pb-16">
        <LegalLanguageNote />
        {children}
      </main>
      <SiteFooter />
    </div>
  );
}
