import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Entrar",
  description: "Entra en Clipaso o crea tu cuenta gratis: 20 minutos de vídeo al mes sin tarjeta.",
};

export default function LoginLayout({ children }: { children: ReactNode }) {
  return children;
}
