"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Trash2Icon } from "lucide-react";
import { toast } from "sonner";

import { AccountSecurity } from "@/components/account-security";
import { UsageMeter } from "@/components/usage-meter";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/client";
import { useDeleteAccount, useMe } from "@/lib/api/hooks";
import { useAuth } from "@/lib/auth";
import { config } from "@/lib/config";

export default function AccountPage() {
  const { session, signOut } = useAuth();
  const { data: me } = useMe();
  const remove = useDeleteAccount();
  const router = useRouter();
  const [confirmation, setConfirmation] = useState("");
  const email = session?.email ?? "";
  const confirmed = confirmation.trim().toLowerCase() === email.toLowerCase() && email !== "";

  async function onDelete() {
    try {
      await remove.mutateAsync();
      await signOut().catch(() => {}); // la cuenta ya no existe: basta con olvidar la sesión local
      toast.success("Tu cuenta y todos tus datos se han eliminado.");
      router.replace("/");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo eliminar la cuenta. Inténtalo de nuevo.");
    }
  }

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">Mi cuenta</h1>

      <Card>
        <CardHeader>
          <CardTitle>Datos de la cuenta</CardTitle>
          <CardDescription>Email con el que inicias sesión y plan actual.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 text-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-muted-foreground">Email</span>
            <span className="font-medium">{email}</span>
          </div>
          {me && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-muted-foreground">Plan</span>
                <Badge variant="secondary">{me.plan.name}</Badge>
              </div>
              <UsageMeter me={me} />
            </>
          )}
        </CardContent>
      </Card>

      {config.authMode === "supabase" && <AccountSecurity />}

      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle>Eliminar cuenta</CardTitle>
          <CardDescription>
            Se borrarán para siempre tu cuenta, todos tus proyectos y clips, y tu historial de consumo. No se puede
            deshacer. Si quieres conservar algún clip, descárgalo antes.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Dialog onOpenChange={(open) => !open && setConfirmation("")}>
            <DialogTrigger render={<Button variant="destructive" />}>
              <Trash2Icon /> Eliminar mi cuenta
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>¿Eliminar tu cuenta definitivamente?</DialogTitle>
                <DialogDescription>
                  Se borrarán tu cuenta, tus proyectos, tus clips y tu historial. Esta acción no se puede deshacer.
                </DialogDescription>
              </DialogHeader>
              <div className="flex flex-col gap-2">
                <Label htmlFor="confirm-email">
                  Para confirmar, escribe tu email: <span className="font-medium">{email}</span>
                </Label>
                <Input
                  id="confirm-email"
                  type="email"
                  autoComplete="off"
                  value={confirmation}
                  onChange={(e) => setConfirmation(e.target.value)}
                />
              </div>
              <DialogFooter>
                <DialogClose render={<Button variant="outline" />}>Cancelar</DialogClose>
                <Button variant="destructive" onClick={onDelete} disabled={!confirmed || remove.isPending}>
                  {remove.isPending ? "Eliminando…" : "Eliminar definitivamente"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          <p className="mt-4 text-xs text-muted-foreground">
            Más información en la <Link href="/legal/privacidad" className="underline underline-offset-4">Política de privacidad</Link>.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
