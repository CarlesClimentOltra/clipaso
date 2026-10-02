"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FolderIcon, GaugeIcon, LifeBuoyIcon, LogOutIcon, PaletteIcon, PlusIcon, SparklesIcon, UserIcon } from "lucide-react";

import { Brand } from "@/components/brand";
import { LanguageSwitcher, ThemeToggle } from "@/components/preferences-controls";
import { UsageRing } from "@/components/usage-meter";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useMe } from "@/lib/api/hooks";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";


export function AppHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const { session, signOut } = useAuth();
  const { data: me } = useMe();
  const initial = (session?.email ?? "?").charAt(0).toUpperCase();
  const { t } = useI18n();
  const nav = [
    { href: "/dashboard", label: t.header.projects, match: ["/dashboard", "/projects"] },
    { href: "/customize", label: t.header.customize, match: ["/customize"] },
    { href: "/plans", label: t.header.plans, match: ["/plans"] },
  ];

  return (
    <header className="sticky top-0 z-30 border-b border-border/60 bg-background/75 backdrop-blur-md">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center gap-6 px-4">
        <Brand href="/dashboard" />
        <nav aria-label="Principal" className="hidden items-center gap-1 rounded-full border bg-card/60 p-1 sm:flex">
          {nav.map((item) => {
            const active = item.match.some((m) => pathname.startsWith(m));
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "rounded-full px-4 py-1.5 text-sm font-medium transition-colors",
                  active ? "bg-foreground text-background" : "text-foreground/70 hover:text-foreground",
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-2 sm:gap-3">
          {me && (
            <Link href="/plans" className="hidden items-center gap-2 rounded-full py-1 pr-3 pl-1 text-xs hover:bg-muted md:flex"
                  title={t.header.usageTitle}>
              <UsageRing me={me} size={30} />
              <span className="leading-tight">
                <span className="block font-medium tabular-nums">
                  {Math.max(0, Math.round(me.usage.remaining_minutes * 10) / 10)} min
                </span>
                <span className="text-muted-foreground">{t.header.available}</span>
              </span>
            </Link>
          )}
          <Link href="/new" className={cn(buttonVariants(), "h-9 rounded-full px-4")}>
            <PlusIcon />
            <span className="hidden sm:inline">{t.header.newProject}</span>
          </Link>
          <span className="hidden items-center lg:flex">
            <LanguageSwitcher />
            <ThemeToggle />
          </span>
          <DropdownMenu>
            <DropdownMenuTrigger
              aria-label={t.header.accountMenu}
              className="flex size-9 items-center justify-center rounded-full bg-brand-soft text-sm font-semibold text-brand-ink ring-1 ring-primary/40 outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              {initial}
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-64">
              <DropdownMenuGroup>
                <DropdownMenuLabel className="flex flex-col gap-1 py-2">
                  <span className="truncate text-sm font-medium text-foreground">{session?.email}</span>
                  {me && (
                    <span>
                      {t.header.plan} <Badge variant="secondary">{t.plans[me.plan.code] ?? me.plan.name}</Badge>
                    </span>
                  )}
                </DropdownMenuLabel>
              </DropdownMenuGroup>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="sm:hidden" onClick={() => router.push("/dashboard")}>
                <FolderIcon /> {t.header.myProjects}
              </DropdownMenuItem>
              <DropdownMenuItem className="sm:hidden" onClick={() => router.push("/customize")}>
                <PaletteIcon /> {t.header.customize}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => router.push("/account")}>
                <UserIcon /> {t.header.account}
              </DropdownMenuItem>
              <DropdownMenuItem className="sm:hidden" onClick={() => router.push("/plans")}>
                <SparklesIcon /> {t.header.plans}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => router.push(`/contacto?desde=${encodeURIComponent(pathname)}`)}>
                <LifeBuoyIcon /> {t.contact.menu}
              </DropdownMenuItem>
              {me?.is_admin && (
                <DropdownMenuItem onClick={() => router.push("/admin")}>
                  <GaugeIcon /> Costes (desarrollo)
                </DropdownMenuItem>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={async () => {
                  await signOut();
                  router.replace("/login");
                }}
              >
                <LogOutIcon /> {t.header.signOut}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}
