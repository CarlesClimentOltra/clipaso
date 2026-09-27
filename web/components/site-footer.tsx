import Link from "next/link";

const LINKS = [
  { href: "/legal/privacidad", label: "Privacidad" },
  { href: "/legal/terminos", label: "Términos" },
  { href: "/legal/cookies", label: "Cookies" },
  { href: "/legal/aviso-legal", label: "Aviso legal" },
];

export function SiteFooter() {
  return (
    <footer className="border-t">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-6 text-sm text-muted-foreground">
        <span>© {new Date().getFullYear()} SmartCuts · Datos alojados en la Unión Europea</span>
        <nav aria-label="Información legal" className="flex flex-wrap gap-x-4 gap-y-1">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} className="hover:text-foreground hover:underline underline-offset-4">
              {l.label}
            </Link>
          ))}
        </nav>
      </div>
    </footer>
  );
}
