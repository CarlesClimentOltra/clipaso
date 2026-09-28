import Link from "next/link";

import { cn } from "@/lib/utils";

/** Marca de SmartCuts: un «play» cortado en diagonal (vídeo + corte inteligente). */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("size-8 shrink-0 rounded-[28%] dark:ring-1 dark:ring-white/20", className)} aria-hidden="true">
      <rect width="32" height="32" rx="9" fill="#0d1608" />
      <path d="M11.5 8.8 23.6 16 11.5 23.2Z" fill="#b6e34a" stroke="#b6e34a" strokeWidth="2.4" strokeLinejoin="round" />
      <path d="M8.5 21.5 21.5 9.5" stroke="#0d1608" strokeWidth="2.6" strokeLinecap="round" />
      <circle cx="24.5" cy="8.5" r="1.6" fill="#b6e34a" />
    </svg>
  );
}

export function Brand({ href = "/", className }: { href?: string; className?: string }) {
  return (
    <Link href={href} className={cn("flex items-center gap-2 rounded-lg outline-none focus-visible:ring-3 focus-visible:ring-ring/50", className)}>
      <BrandMark />
      <span className="text-[1.05rem] font-semibold tracking-tight">
        Smart<span className="text-brand-ink">Cuts</span>
      </span>
    </Link>
  );
}
