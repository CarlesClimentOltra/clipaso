"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AdminMessages } from "@/components/admin-messages";
import { PageHeader } from "@/components/page-header";
import { Segmented } from "@/components/segmented";
import { Skeleton } from "@/components/ui/skeleton";
import { useAdminUsage, useMe } from "@/lib/api/hooks";
import { useI18n } from "@/lib/i18n";
import { MODES } from "@/lib/modes";

const usd = (v: number | null | undefined, digits = 4) => (v == null ? "—" : `$${v.toFixed(digits)}`);

/** Panel de costes (solo cuentas de desarrollo): cuánto cuesta de verdad cada modo. Solo en español. */
export default function AdminPage() {
  const router = useRouter();
  const { data: me } = useMe();
  const [days, setDays] = useState("30");
  const { data, isPending } = useAdminUsage(Number(days), !!me?.is_admin);
  const { t, formatDate } = useI18n();

  useEffect(() => {
    if (me && !me.is_admin) router.replace("/dashboard");
  }, [me, router]);
  if (!me?.is_admin) return null;
  const name = (mode: string) => (t.newProject.modes as Record<string, { title: string }>)[mode]?.title ?? mode;

  return (
    <div className="flex flex-col gap-8">
      <PageHeader eyebrow="Desarrollador" title="Costes reales"
                  description="Lo que cuesta cada proyecto en Modal (GPU, CPU y memoria) y en IA. Solo lo ven las cuentas de desarrollo."
                  actions={<Segmented label="Periodo" value={days} onChange={setDays}
                                      options={[{ value: "7", label: "7 días" }, { value: "30", label: "30 días" },
                                                { value: "90", label: "90 días" }]} />} />
      {isPending || !data ? (
        <Skeleton className="h-64 w-full rounded-3xl" />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-4">
            {[
              ["Proyectos", String(data.jobs)],
              ["Cómputo (Modal)", usd(data.compute_usd, 2)],
              ["IA (Anthropic)", usd(data.llm_usd, 2)],
              ["Tareas (re-render, descargas…)", `${data.tasks} · ${usd(data.task_compute_usd, 2)}`],
            ].map(([label, value]) => (
              <div key={label} className="rounded-2xl border bg-card p-4">
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className="text-2xl font-semibold tabular-nums">{value}</p>
              </div>
            ))}
          </div>

          <section className="flex flex-col gap-3">
            <h2 className="text-lg font-semibold">Por modo</h2>
            <div className="overflow-x-auto rounded-2xl border bg-card">
              <table className="w-full text-sm">
                <thead className="border-b text-left text-xs text-muted-foreground">
                  <tr>
                    {["Modo", "Proyectos", "Medidos", "Minutos", "Seg. worker", "Cómputo", "IA", "MB subidos", "$/min"]
                      .map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {data.modes.map((m) => (
                    <tr key={m.mode} className="border-b last:border-0">
                      <td className="px-3 py-2 font-medium">{name(m.mode)}</td>
                      <td className="px-3 py-2 tabular-nums">{m.jobs}</td>
                      <td className="px-3 py-2 tabular-nums">{m.measured}</td>
                      <td className="px-3 py-2 tabular-nums">{m.minutes.toFixed(1)}</td>
                      <td className="px-3 py-2 tabular-nums">{m.worker_s.toFixed(0)}</td>
                      <td className="px-3 py-2 tabular-nums">{usd(m.compute_usd)}</td>
                      <td className="px-3 py-2 tabular-nums">{usd(m.llm_usd)}</td>
                      <td className="px-3 py-2 tabular-nums">{m.source_mb.toFixed(0)}</td>
                      <td className="px-3 py-2 font-semibold tabular-nums">{usd(m.usd_per_minute)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="flex flex-col gap-3">
            <h2 className="text-lg font-semibold">Últimos proyectos</h2>
            <div className="overflow-x-auto rounded-2xl border bg-card">
              <table className="w-full text-xs">
                <thead className="border-b text-left text-muted-foreground">
                  <tr>
                    {["Fecha", "Usuario", "Modo", "Estado", "Min", "MB", "Resolución", "Worker", "CPU", "Cómputo", "IA",
                      "Etapas (s)"].map((h) => <th key={h} className="px-3 py-2 font-medium whitespace-nowrap">{h}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {data.recent.map((j) => (
                    <tr key={j.id} className="border-b align-top last:border-0">
                      <td className="px-3 py-2 whitespace-nowrap">
                        {formatDate(j.created_at, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
                      </td>
                      <td className="max-w-40 truncate px-3 py-2">{j.user}</td>
                      <td className="px-3 py-2 whitespace-nowrap">{MODES.find((m) => m.id === j.mode) ? name(j.mode) : j.mode}</td>
                      <td className="px-3 py-2">{j.status}</td>
                      <td className="px-3 py-2 tabular-nums">{j.minutes.toFixed(1)}</td>
                      <td className="px-3 py-2 tabular-nums">{j.source_mb?.toFixed(0) ?? "—"}</td>
                      <td className="px-3 py-2">{j.source_res ?? "—"}</td>
                      <td className="px-3 py-2 tabular-nums">{j.worker_s != null ? `${j.worker_s.toFixed(0)} s` : "—"}</td>
                      <td className="px-3 py-2 tabular-nums">{j.cpu_s != null ? `${j.cpu_s.toFixed(0)} s` : "—"}</td>
                      <td className="px-3 py-2 tabular-nums">{usd(j.compute_usd)}</td>
                      <td className="px-3 py-2 tabular-nums">{usd(j.llm_usd)}</td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {Object.entries(j.stages).map(([k, v]) => `${k} ${v.toFixed(0)}`).join(" · ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
      {me?.is_admin && <AdminMessages />}
    </div>
  );
}
