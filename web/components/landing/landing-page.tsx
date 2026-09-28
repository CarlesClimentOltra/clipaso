"use client";

import Link from "next/link";
import { ArrowRightIcon, CheckIcon, ChevronDownIcon } from "lucide-react";

import { Brand } from "@/components/brand";
import { Examples } from "@/components/landing/examples";
import { FeatureGrid } from "@/components/landing/feature-grid";
import { FeatureMarquee } from "@/components/landing/feature-marquee";
import { HeroVisual } from "@/components/landing/hero-visual";
import { LanguageSwitcher, ThemeToggle } from "@/components/preferences-controls";
import { Pricing } from "@/components/pricing";
import { SiteFooter } from "@/components/site-footer";
import { buttonVariants } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

function SectionHeading({ eyebrow, title, lead, center }: { eyebrow: string; title: string; lead?: string; center?: boolean }) {
  return (
    <div className={cn("flex max-w-2xl flex-col gap-3", center && "mx-auto items-center text-center")}>
      <span className="text-sm font-medium text-brand-ink">{eyebrow}</span>
      <h2 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">{title}</h2>
      {lead && <p className="text-pretty text-muted-foreground">{lead}</p>}
    </div>
  );
}

export function LandingPage() {
  const { t, locale } = useI18n();
  const l = t.landing;
  const nav = [
    { href: "#como-funciona", label: l.nav.how },
    { href: "#ejemplos", label: l.nav.examples },
    { href: "#funciones", label: l.nav.features },
    { href: "#precios", label: l.nav.pricing },
    { href: "#preguntas", label: l.nav.faq },
  ];

  return (
    <div className="flex flex-1 flex-col overflow-x-clip" lang={locale}>
      <header className="sticky top-0 z-40 bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-6 px-4">
          <Brand href={locale === "en" ? "/en" : "/"} />
          <nav aria-label={l.navLabel} className="hidden items-center gap-6 text-sm font-medium lg:flex">
            {nav.map((item) => (
              <a key={item.href} href={item.href} className="text-foreground/75 transition-colors hover:text-foreground">
                {item.label}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-1 sm:gap-2">
            <LanguageSwitcher className="hidden sm:inline-flex" />
            <ThemeToggle className="hidden sm:inline-flex" />
            <Link href="/login" className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "hidden sm:inline-flex")}>
              {l.signIn}
            </Link>
            <Link href="/login" className={cn(buttonVariants({ size: "lg" }), "rounded-full px-4")}>
              {l.startFree} <ArrowRightIcon />
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
                {l.badge}
              </span>
              <h1 className="text-4xl leading-[1.05] font-semibold tracking-tight text-balance sm:text-6xl">
                {l.titleStart} <em className="font-semibold text-brand-ink">{l.titleAccent}</em>
              </h1>
              <p className="max-w-xl text-lg text-pretty text-muted-foreground">{l.lead}</p>
              <div className="flex flex-wrap gap-3">
                <Link href="/login" className={cn(buttonVariants({ size: "lg" }), "h-11 rounded-full px-6 text-base")}>
                  {l.startFree} <ArrowRightIcon />
                </Link>
                <a href="#como-funciona" className={cn(buttonVariants({ variant: "outline", size: "lg" }), "h-11 rounded-full px-6 text-base")}>
                  {l.howButton}
                </a>
              </div>
              <ul className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-muted-foreground">
                {l.trust.map((item) => (
                  <li key={item} className="flex items-center gap-1.5">
                    <CheckIcon className="size-4 text-brand-ink" /> {item}
                  </li>
                ))}
              </ul>
            </div>
            <HeroVisual />
          </div>
        </section>

        <FeatureMarquee />

        <section id="como-funciona" className="scroll-mt-20">
          <div className="mx-auto flex w-full max-w-6xl flex-col gap-12 px-4 py-24">
            <SectionHeading eyebrow={l.how.eyebrow} title={l.how.title} />
            <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {l.how.steps.map(([title, text], i) => (
                <li key={title} className="flex flex-col gap-4 rounded-3xl border bg-card p-6">
                  <span className="flex size-10 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                    {i + 1}
                  </span>
                  <h3 className="font-semibold">{title}</h3>
                  <p className="text-sm text-pretty text-muted-foreground">{text}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section id="ejemplos" className="scroll-mt-20 bg-muted/40">
          <div className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-4 py-24">
            <SectionHeading eyebrow={l.examples.eyebrow} title={l.examples.title} lead={l.examples.lead} />
            <Examples />
          </div>
        </section>

        <section id="funciones" className="scroll-mt-20">
          <div className="mx-auto flex w-full max-w-6xl flex-col gap-12 px-4 py-24">
            <SectionHeading eyebrow={l.features.eyebrow} title={l.features.title} />
            <FeatureGrid />
          </div>
        </section>

        <section id="precios" className="scroll-mt-20 bg-muted/40">
          <div className="mx-auto flex w-full max-w-6xl flex-col gap-12 px-4 py-24">
            <SectionHeading eyebrow={l.pricing.eyebrow} title={l.pricing.title} lead={l.pricing.lead} center />
            <Pricing />
          </div>
        </section>

        <section id="preguntas" className="scroll-mt-20">
          <div className="mx-auto grid w-full max-w-6xl gap-10 px-4 py-24 lg:grid-cols-[1fr_1.6fr]">
            <SectionHeading eyebrow={l.faq.eyebrow} title={l.faq.title} lead={l.faq.lead} />
            <div className="flex flex-col gap-3">
              {l.faq.items.map(([q, a]) => (
                <details key={q} className="group rounded-2xl border bg-card px-5 py-4 open:shadow-sm">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium [&::-webkit-details-marker]:hidden">
                    {q}
                    <ChevronDownIcon className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
                  </summary>
                  <p className="mt-3 text-sm text-pretty text-muted-foreground">{a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="px-4 py-24">
          <div className="relative isolate mx-auto flex w-full max-w-6xl flex-col items-center gap-6 overflow-hidden rounded-[2rem] bg-slate-950 px-6 py-16 text-center text-white ring-1 ring-white/10">
            <div className="absolute -top-24 left-1/2 -z-10 size-96 -translate-x-1/2 rounded-full bg-lime-300/20 blur-3xl" />
            <h2 className="text-3xl font-semibold tracking-tight text-balance sm:text-5xl">{l.cta.title}</h2>
            <p className="max-w-xl text-white/70">{l.cta.lead}</p>
            <Link href="/login" className={cn(buttonVariants({ size: "lg" }), "h-11 rounded-full px-6 text-base")}>
              {l.cta.button} <ArrowRightIcon />
            </Link>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
