"use client";

import { UploadForm } from "@/components/upload-form";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMe } from "@/lib/api/hooks";

export default function NewProjectPage() {
  const { data: me, error } = useMe();

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Nuevo proyecto</h1>
        <p className="text-sm text-muted-foreground">
          Sube un vídeo con diálogo (entrevista, podcast, charla…) y elegiremos los momentos con más gancho.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Tu vídeo</CardTitle>
          <CardDescription>Los clips se generan en vertical 9:16 con subtítulos, listos para TikTok, Reels y Shorts.</CardDescription>
        </CardHeader>
        <CardContent>
          {error ? (
            <p className="text-sm text-destructive">{error.message}</p>
          ) : me ? (
            <UploadForm me={me} />
          ) : (
            <Skeleton className="h-64 w-full" />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
