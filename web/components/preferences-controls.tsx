"use client";

import { usePathname, useRouter } from "next/navigation";
import { CheckIcon, LanguagesIcon, MonitorIcon, MoonIcon, SunIcon } from "lucide-react";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useI18n, type Locale } from "@/lib/i18n";

const LANGUAGE_NAMES: Record<Locale, string> = { es: "Español", en: "English" };
// Las portadas públicas tienen una URL por idioma (buscadores); el resto de páginas usa la preferencia.
const LANDING: Record<Locale, string> = { es: "/", en: "/en" };

const subscribeNothing = () => () => {};

/** El tema real solo se conoce en el navegador: hasta entonces se pinta un icono neutro. */
function useMounted() {
  return useSyncExternalStore(subscribeNothing, () => true, () => false);
}

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme();
  const { t } = useI18n();
  const mounted = useMounted();
  const options = [
    { value: "light", label: t.common.themeLight, icon: SunIcon },
    { value: "dark", label: t.common.themeDark, icon: MoonIcon },
    { value: "system", label: t.common.themeSystem, icon: MonitorIcon },
  ];
  const current = options.find((o) => o.value === theme) ?? options[2];
  const Icon = mounted ? current.icon : MonitorIcon;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={<Button variant="ghost" size="icon-sm" className={className} aria-label={t.common.toggleTheme} />}
      >
        <Icon />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-40">
        {options.map(({ value, label, icon: ItemIcon }) => (
          <DropdownMenuItem key={value} onClick={() => setTheme(value)}>
            <ItemIcon /> {label}
            {mounted && theme === value && <CheckIcon className="ml-auto" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function LanguageSwitcher({ className, onChange }: { className?: string; onChange?: (locale: Locale) => void }) {
  const { locale, setLocale, t } = useI18n();
  const pathname = usePathname();
  const router = useRouter();

  function choose(next: Locale) {
    setLocale(next);
    onChange?.(next);
    if (pathname === "/" || pathname === "/en") router.push(LANDING[next]);
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={<Button variant="ghost" size="sm" className={className} aria-label={t.common.language} />}
      >
        <LanguagesIcon /> {locale.toUpperCase()}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-40">
        {(Object.keys(LANGUAGE_NAMES) as Locale[]).map((l) => (
          <DropdownMenuItem key={l} onClick={() => choose(l)}>
            {LANGUAGE_NAMES[l]}
            {l === locale && <CheckIcon className="ml-auto" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
