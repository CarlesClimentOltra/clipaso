"use client";

import Link from "next/link";

import { LanguageSwitcher, ThemeToggle } from "@/components/preferences-controls";
import { useI18n } from "@/lib/i18n";
import { legal } from "@/lib/legal";

export function SiteFooter() {
  const { t } = useI18n();
  const links = [
    { href: "/legal/privacidad", label: t.footer.privacy },
    { href: "/legal/terminos", label: t.footer.terms },
    { href: "/legal/cookies", label: t.footer.cookies },
    { href: "/legal/reembolsos", label: t.footer.refunds },
    { href: "/legal/aviso-legal", label: t.footer.notice },
  ];
  return (
    <footer className="border-t">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-3 px-4 py-6 text-sm text-muted-foreground">
        <span>© {new Date().getFullYear()} Clipaso · {t.footer.rights}</span>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <nav aria-label={t.footer.legalNav} className="flex flex-wrap gap-x-4 gap-y-1">
            {links.map((l) => (
              <Link key={l.href} href={l.href} className="underline-offset-4 hover:text-foreground hover:underline">
                {l.label}
              </Link>
            ))}
            <a href={`mailto:${legal.owner.email}`} className="underline-offset-4 hover:text-foreground hover:underline">
              {t.footer.contact}
            </a>
          </nav>
          <span className="flex items-center gap-1">
            <LanguageSwitcher />
            <ThemeToggle />
          </span>
        </div>
      </div>
    </footer>
  );
}
