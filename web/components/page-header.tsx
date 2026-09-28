import type { ReactNode } from "react";

/** Cabecera de página de la app: antetítulo en lima, título grande y acciones a la derecha. */
export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="flex min-w-0 flex-col gap-1.5">
        {eyebrow && <span className="text-sm font-medium text-brand-ink">{eyebrow}</span>}
        <h1 className="text-3xl font-semibold tracking-tight text-balance">{title}</h1>
        {description && <p className="max-w-2xl text-pretty text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
