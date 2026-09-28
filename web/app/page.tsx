import Link from "next/link";
import { ArrowRightIcon, CheckIcon, ChevronDownIcon } from "lucide-react";

import { Brand } from "@/components/brand";
import { FeatureGrid } from "@/components/landing/feature-grid";
import { FeatureMarquee } from "@/components/landing/feature-marquee";
import { HeroVisual } from "@/components/landing/hero-visual";
import { Pricing } from "@/components/pricing";
import { SiteFooter } from "@/components/site-footer";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "#como-funciona", label: "Cómo funciona" },
  { href: "#funciones", label: "Funciones" },
  { href: "#precios", label: "Precios" },
  { href: "#preguntas", label: "Preguntas" },
];

const STEPS = [
  { title: "Sube tu vídeo", text: "Entrevistas, podcasts, charlas o directos. Si se corta la conexión, la subida continúa donde se quedó." },
  { title: "La IA elige los mejores momentos", text: "Frases con gancho, historias completas y remates que funcionan solos, con su texto para publicar." },
  { title: "Encuadre y subtítulos automáticos", text: "Sigue la cara de quien habla, adapta el plano al formato y añade subtítulos palabra a palabra." },
  { title: "Retoca y descarga", text: "Ajusta el corte o corrige una palabra en el editor, y descarga todos tus clips de una vez." },
];

const FAQ = [
  {
    q: "¿Qué vídeos funcionan mejor?",
    a: "Los que tienen conversación: podcasts, entrevistas, charlas, clases o directos. SmartCuts elige los momentos a partir de lo que se dice, así que necesita diálogo.",
  },
  {
    q: "¿Cuánto tarda?",
    a: "Unos pocos minutos para un vídeo de media hora. Te avisamos por email cuando tus clips están listos, así que puedes cerrar la pestaña.",
  },
  {
    q: "¿Puedo editar los clips?",
    a: "Sí. Desde el editor puedes mover el inicio y el final, corregir palabras de los subtítulos, cambiar el estilo y volver a generar el clip. También puedes pedir más clips del mismo vídeo sin gastar minutos.",
  },
  {
    q: "¿En qué idiomas funciona?",
    a: "En español, inglés, portugués, francés, italiano y alemán, entre otros. También puede detectar el idioma automáticamente.",
  },
  {
    q: "¿Usáis mis vídeos para entrenar IA?",
    a: "No. Tus vídeos se procesan en servidores de la Unión Europea solo para crear tus clips, y el original se borra cuando termina el proyecto (o antes, si lo prefieres).",
  },
  {
    q: "¿Necesito tarjeta para probarlo?",
    a: "No. El plan Gratis incluye 30 minutos de vídeo al mes, sin tarjeta y sin compromiso.",
  },
];

export default function Home() {
  return (
    <div className="flex flex-1 flex-col overflow-x-clip">
      <header className="sticky top-0 z-40 bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-6 px-4">
          <Brand />
          <nav aria-label="Principal" className="hidden items-center gap-7 text-sm font-medium md:flex">
            {NAV.map((item) => (
              <a key={item.href} href={item.href} className="text-foreground/75 transition-colors hover:text-foreground">
                {item.label}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <Link href="/login" className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "hidden sm:inline-flex")}>
              Entrar
            </Link>
            <Link href="/login" className={cn(buttonVariants({ size: "lg" }), "rounded-full px-4")}>
              Empieza gratis <ArrowRightIcon />
            </Link>
          </div>
        </div>
      </header>

      <main className="flex flex-col">
        {/* Hero */}
        <section className="relative isolate">
          <div className="absolute inset-y-0 right-0 -z-10 hidden w-3/5 bg-linear-to-l from-brand-soft via-brand-soft/50 to-transparent lg:block" />
          <div className="mx-auto grid w-full max-w-6xl items-center gap-14 px-4 pt-12 pb-20 lg:grid-cols-[1fr_1.05fr] lg:pt-20 lg:pb-28">
            <div className="flex flex-col items-start gap-7">
              <span className="rounded-full border border-primary/50 bg-brand-soft px-4 py-1.5 text-sm font-medium text-brand-ink">
                Clips con IA para creadores
              </span>
              <h1 className="text-4xl leading-[1.05] font-semibold tracking-tight text-balance sm:text-6xl">
                Convierte tus vídeos largos en <em className="font-semibold text-brand-ink">clips virales</em>
              </h1>
              <p className="max-w-xl text-lg text-pretty text-muted-foreground">
                SmartCuts encuentra los mejores momentos de tus vídeos y los convierte en clips verticales con
                subtítulos, listos para TikTok, Instagram Reels y YouTube Shorts. Sin editar a mano.
              </p>
              <div className="flex flex-wrap gap-3">
                <Link href="/login" className={cn(buttonVariants({ size: "lg" }), "h-11 rounded-full px-6 text-base")}>
                  Empieza gratis <ArrowRightIcon />
                </Link>
                <a
                  href="#como-funciona"
                  className={cn(buttonVariants({ variant: "outline", size: "lg" }), "h-11 rounded-full px-6 text-base")}
                >
                  Cómo funciona
                </a>
              </div>
              <ul className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-muted-foreground">
                {["30 min gratis al mes", "Sin tarjeta", "Datos en la UE"].map((t) => (
                  <li key={t} className="flex items-center gap-1.5">
                    <CheckIcon className="size-4 text-brand-ink" /> {t}
                  </li>
                ))}
              </ul>
            </div>
            <HeroVisual />
          </div>
        </section>

        <FeatureMarquee />

        {/* Cómo funciona */}
        <section id="como-funciona" className="scroll-mt-20">
          <div className="mx-auto flex w-full max-w-6xl flex-col gap-12 px-4 py-24">
            <div className="flex max-w-2xl flex-col gap-3">
              <span className="text-sm font-medium text-brand-ink">Cómo funciona</span>
              <h2 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
                De una hora de vídeo a una semana de contenido
              </h2>
            </div>
            <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {STEPS.map((step, i) => (
                <li key={step.title} className="flex flex-col gap-4 rounded-3xl border bg-card p-6">
                  <span className="flex size-10 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                    {i + 1}
                  </span>
                  <h3 className="font-semibold">{step.title}</h3>
                  <p className="text-sm text-pretty text-muted-foreground">{step.text}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Funciones */}
        <section id="funciones" className="scroll-mt-20 bg-muted/40">
          <div className="mx-auto flex w-full max-w-6xl flex-col gap-12 px-4 py-24">
            <div className="flex max-w-2xl flex-col gap-3">
              <span className="text-sm font-medium text-brand-ink">Funciones</span>
              <h2 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
                Todo lo que necesitas para publicar, en un solo sitio
              </h2>
            </div>
            <FeatureGrid />
          </div>
        </section>

        {/* Precios */}
        <section id="precios" className="scroll-mt-20">
          <div className="mx-auto flex w-full max-w-6xl flex-col gap-12 px-4 py-24">
            <div className="flex flex-col items-center gap-3 text-center">
              <span className="text-sm font-medium text-brand-ink">Precios</span>
              <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">Planes sencillos</h2>
              <p className="max-w-xl text-muted-foreground">
                Pagas por minutos de vídeo procesados. Editar y pedir más clips de un vídeo no gasta minutos.
              </p>
            </div>
            <Pricing />
          </div>
        </section>

        {/* Preguntas frecuentes */}
        <section id="preguntas" className="scroll-mt-20 bg-muted/40">
          <div className="mx-auto grid w-full max-w-6xl gap-10 px-4 py-24 lg:grid-cols-[1fr_1.6fr]">
            <div className="flex flex-col gap-3">
              <span className="text-sm font-medium text-brand-ink">Preguntas frecuentes</span>
              <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">¿Tienes dudas?</h2>
              <p className="text-muted-foreground">Si no encuentras la respuesta, escríbenos y te ayudamos.</p>
            </div>
            <div className="flex flex-col gap-3">
              {FAQ.map((item) => (
                <details key={item.q} className="group rounded-2xl border bg-card px-5 py-4 open:shadow-sm">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium [&::-webkit-details-marker]:hidden">
                    {item.q}
                    <ChevronDownIcon className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
                  </summary>
                  <p className="mt-3 text-sm text-pretty text-muted-foreground">{item.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* Llamada final */}
        <section className="px-4 py-24">
          <div className="relative isolate mx-auto flex w-full max-w-6xl flex-col items-center gap-6 overflow-hidden rounded-[2rem] bg-slate-950 px-6 py-16 text-center text-white">
            <div className="absolute -top-24 left-1/2 -z-10 size-96 -translate-x-1/2 rounded-full bg-lime-300/20 blur-3xl" />
            <h2 className="text-3xl font-semibold tracking-tight text-balance sm:text-5xl">
              Tu próximo clip viral ya está en tus vídeos
            </h2>
            <p className="max-w-xl text-white/70">
              Sube uno y en unos minutos tendrás clips listos para publicar. Gratis, sin tarjeta.
            </p>
            <Link href="/login" className={cn(buttonVariants({ size: "lg" }), "h-11 rounded-full px-6 text-base")}>
              Crear mis primeros clips <ArrowRightIcon />
            </Link>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
