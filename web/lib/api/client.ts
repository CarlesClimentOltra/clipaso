// Cliente tipado de la API. Los tipos salen de `schema.d.ts`, generado desde el
// OpenAPI de FastAPI (`npm run gen:api`), así frontend y backend no se desincronizan.

import createClient from "openapi-fetch";

import { config } from "@/lib/config";
import { dictionary } from "@/lib/i18n";
import { getLocale } from "@/lib/i18n/store";
import type { components, paths } from "@/lib/api/schema";

export type Schemas = components["schemas"];
export type Me = Schemas["MeOut"];
export type Plan = Schemas["PlanOut"];
export type Job = Schemas["JobOut"];
export type JobSummary = Schemas["JobSummary"];
export type Clip = Schemas["ClipOut"];

/** Error con mensaje ya traducido para mostrar al usuario. */
export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export function createApi(getToken: () => Promise<string | null>) {
  const client = createClient<paths>({ baseUrl: config.apiUrl });
  client.use({
    async onRequest({ request }) {
      const token = await getToken();
      if (token) request.headers.set("Authorization", `Bearer ${token}`);
      // Los mensajes de error de la API llegan en el idioma de la interfaz.
      request.headers.set("Accept-Language", getLocale());
      return request;
    },
  });
  return client;
}

export type Api = ReturnType<typeof createApi>;

/** Desenvuelve la respuesta de openapi-fetch lanzando `ApiError` con el mensaje de la API. */
export async function unwrap<T>(
  promise: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  let result;
  try {
    result = await promise;
  } catch {
    throw new ApiError("network_error", dictionary().errors.network_error, 0);
  }
  const { data, error, response } = result;
  if (error !== undefined || !response.ok) {
    const body = (error ?? {}) as { error?: { code?: string; message?: string } };
    throw new ApiError(
      body.error?.code ?? "internal_error",
      body.error?.message ?? dictionary().errors.unexpected,
      response.status,
    );
  }
  return data as T;
}

export type JobOptions = Schemas["JobOptions"];
export type CaptionStyle = Schemas["CaptionStyle"];
export type CaptionPreset = Schemas["CaptionPreset"];
export type UserStyle = Schemas["UserStyle"];
export type ClipExport = Schemas["ExportOut"];
export type ExportRequest = Schemas["ExportIn"];
export type UserStyles = Schemas["StylesOut"];
export type BrandingPrefs = Schemas["BrandingPrefs"];
export type Preferences = Schemas["PreferencesOut"];
export type ClipOptions = Schemas["OptionsOut"];
export type Editor = Schemas["EditorOut"];
export type EditorWord = Schemas["EditorWordOut"];
