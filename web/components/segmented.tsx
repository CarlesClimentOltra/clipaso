"use client";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

type Option<T extends string> = { value: T; label: React.ReactNode; title?: string };

/** Elección única entre pocas opciones (siempre hay una seleccionada). */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
  disabled,
}: {
  value: T;
  onChange: (value: T) => void;
  options: Option<T>[];
  label: string;
  disabled?: boolean;
}) {
  return (
    <ToggleGroup
      aria-label={label}
      variant="outline"
      size="sm"
      spacing={0}
      value={[value]}
      disabled={disabled}
      onValueChange={(values: unknown[]) => {
        const next = values[values.length - 1];
        if (typeof next === "string") onChange(next as T);
      }}
    >
      {options.map((o) => (
        <ToggleGroupItem key={o.value} value={o.value} title={o.title} className="px-3">
          {o.label}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}
