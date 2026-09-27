import Link from "next/link";
import { CaptionsIcon, CropIcon, SparklesIcon, UploadCloudIcon } from "lucide-react";

import { Brand } from "@/components/brand";
import { Pricing } from "@/components/pricing";
import { buttonVariants } from "@/components/ui/button";

const STEPS = [
  { icon: UploadCloudIcon, title: "Sube tu vídeo", text: "Entrevistas, podcasts, charlas o directos. Hasta varias horas." },
  { icon: SparklesIcon, title: "La IA elige los mejores momentos", text: "Frases con gancho, historias completas y remates que funcionan solos." },
  { icon: CropIcon, title: "Encuadre vertical automático", text: "Sigue la cara de quien habla y adapta el plano a 9:16." },
  { icon: CaptionsIcon, title: "Subtítulos que retienen", text: "Palabra a palabra, resaltados y listos para publicar." },
];

export default function Home() {
  return (
    <div className="flex flex-1 flex-col">
      <header className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4">
        <Brand />
        <nav className="flex items-center gap-2">
          <Link href="#precios" className={buttonVariants({ variant: "ghost", size: "sm" })}>
            Precios
          </Link>
          <Link href="/login" className={buttonVariants({ size: "sm" })}>
            Entrar
          </Link>
        </nav>
      </header>

      <main className="flex flex-col">
        <section className="mx-auto flex w-full max-w-4xl flex-col items-center gap-6 px-4 py-20 text-center sm:py-28">
          <h1 className="text-4xl font-semibold tracking-tight text-balance sm:text-6xl">
            De un vídeo largo a clips virales, <span className="text-primary">en minutos</span>
          </h1>
          <p className="max-w-2xl text-lg text-pretty text-muted-foreground">
            SmartCuts encuentra los mejores momentos de tus vídeos y los convierte en clips verticales con subtítulos,
            listos para TikTok, Instagram Reels y YouTube Shorts.
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <Link href="/login" className={buttonVariants({ size: "lg", className: "h-11 px-5 text-base" })}>
              Empieza gratis
            </Link>
            <Link href="#como-funciona" className={buttonVariants({ variant: "outline", size: "lg", className: "h-11 px-5 text-base" })}>
              Cómo funciona
            </Link>
          </div>
          <p className="text-sm text-muted-foreground">30 minutos de vídeo gratis cada mes · sin tarjeta</p>
        </section>

        <section id="como-funciona" className="border-y bg-muted/30">
          <div className="mx-auto grid w-full max-w-6xl gap-8 px-4 py-16 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map(({ icon: Icon, title, text }) => (
              <div key={title} className="flex flex-col gap-3">
                <span className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <Icon className="size-5" />
                </span>
                <h2 className="font-semibold">{title}</h2>
                <p className="text-sm text-muted-foreground">{text}</p>
              </div>
            ))}
          </div>
        </section>

        <section id="precios" className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 py-20">
          <div className="text-center">
            <h2 className="text-3xl font-semibold tracking-tight">Planes sencillos</h2>
            <p className="text-muted-foreground">Pagas por minutos de vídeo procesados. Cambia de plan cuando quieras.</p>
          </div>
          <Pricing />
        </section>
      </main>

      <footer className="border-t">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-6 text-sm text-muted-foreground">
          <span>© {new Date().getFullYear()} SmartCuts</span>
          <span>Datos alojados en la Unión Europea</span>
        </div>
      </footer>
    </div>
  );
}
