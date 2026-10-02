import type { Metadata } from "next";
import type { ReactNode } from "react";

import { Brand } from "@/components/brand";
import { SiteFooter } from "@/components/site-footer";

export const metadata: Metadata = {
  title: "Contacto",
  description: "Escríbenos con tus dudas, sugerencias o errores que hayas encontrado en Clipaso.",
};

export default function ContactLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-1 flex-col">
      <header className="mx-auto flex h-16 w-full max-w-2xl items-center px-4">
        <Brand />
      </header>
      <main className="mx-auto w-full max-w-2xl flex-1 px-4 pt-6 pb-16">{children}</main>
      <SiteFooter />
    </div>
  );
}
