"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOutIcon, PlusIcon } from "lucide-react";

import { Brand } from "@/components/brand";
import { UsageMeter } from "@/components/usage-meter";
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
import { cn } from "@/lib/utils";

const NAV = [{ href: "/dashboard", label: "Mis proyectos" }];

export function AppHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const { session, signOut } = useAuth();
  const { data: me } = useMe();

  const initial = (session?.email ?? "?").charAt(0).toUpperCase();

  return (
    <header className="sticky top-0 z-30 border-b bg-background/85 backdrop-blur">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-4 px-4">
        <Brand href="/dashboard" />
        <nav className="hidden items-center gap-1 sm:flex">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                buttonVariants({ variant: "ghost", size: "sm" }),
                pathname.startsWith(item.href) && "bg-muted text-foreground",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          {me && <UsageMeter me={me} className="hidden w-48 md:flex" />}
          <Link href="/new" className={buttonVariants({ size: "sm" })}>
            <PlusIcon />
            <span className="hidden sm:inline">Nuevo proyecto</span>
          </Link>
          <DropdownMenu>
            <DropdownMenuTrigger
              aria-label="Menú de cuenta"
              className="flex size-8 items-center justify-center rounded-full bg-muted text-sm font-medium outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              {initial}
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-64">
              <DropdownMenuGroup>
                <DropdownMenuLabel className="flex flex-col gap-1 py-2">
                  <span className="truncate text-sm font-medium text-foreground">{session?.email}</span>
                  {me && (
                    <span>
                      Plan <Badge variant="secondary">{me.plan.name}</Badge>
                    </span>
                  )}
                </DropdownMenuLabel>
              </DropdownMenuGroup>
              {me && (
                <div className="px-1.5 pb-2 md:hidden">
                  <UsageMeter me={me} />
                </div>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={async () => {
                  await signOut();
                  router.replace("/login");
                }}
              >
                <LogOutIcon />
                Cerrar sesión
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}
