"use client";

// Sesión del usuario. La interfaz no sabe qué proveedor hay detrás:
// - dev: token "dev:<email>" guardado en localStorage (solo desarrollo local).
// - supabase: sesión de Supabase Auth; el token de acceso se envía a nuestra API.

import { createClient, type Session as SbSession, type SupabaseClient } from "@supabase/supabase-js";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import { config } from "@/lib/config";

// `hasPassword`: la cuenta puede entrar con email y contraseña (no solo con Google).
type Session = { email: string; token: string; hasPassword: boolean };

type AuthContextValue = {
  session: Session | null;
  loading: boolean;
  signIn: (email: string, password: string, captchaToken?: string) => Promise<void>;
  signUp: (email: string, password: string, captchaToken?: string) => Promise<{ needsConfirmation: boolean }>;
  signInWithGoogle: () => Promise<void>;
  /** Envía el email con el enlace para elegir una contraseña nueva. */
  requestPasswordReset: (email: string, captchaToken?: string) => Promise<void>;
  /** Cambia la contraseña de la sesión actual (tras el enlace de recuperación o desde «Mi cuenta»). */
  updatePassword: (password: string) => Promise<void>;
  /** Pide el cambio de email; Supabase envía un enlace de confirmación. */
  updateEmail: (email: string) => Promise<void>;
  signOut: () => Promise<void>;
  getToken: () => Promise<string | null>;
};

const DEV_KEY = "smartcuts.dev-session";
const AuthContext = createContext<AuthContextValue | null>(null);

let supabase: SupabaseClient | null = null;
function getSupabase(): SupabaseClient {
  supabase ??= createClient(config.supabaseUrl, config.supabaseAnonKey);
  return supabase;
}

// Sesión de desarrollo como "store externo": se lee con useSyncExternalStore y se
// sincroniza entre pestañas con el evento `storage`.
const devListeners = new Set<() => void>();
let devMemory: string | null = null; // respaldo si localStorage no está disponible

function getDevRaw(): string | null {
  try {
    return localStorage.getItem(DEV_KEY);
  } catch {
    return devMemory;
  }
}

function writeDevRaw(raw: string | null) {
  devMemory = raw;
  try {
    if (raw === null) localStorage.removeItem(DEV_KEY);
    else localStorage.setItem(DEV_KEY, raw);
  } catch {
    // se queda en memoria
  }
  devListeners.forEach((l) => l());
}

function subscribeDev(listener: () => void) {
  devListeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    devListeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

function parseDev(raw: string | null | undefined): Session | null {
  if (!raw) return null;
  try {
    return { hasPassword: false, ...(JSON.parse(raw) as Omit<Session, "hasPassword">) };
  } catch {
    return null;
  }
}

function fromSupabase(s: SbSession | null): Session | null {
  if (!s) return null;
  const meta = s.user.app_metadata ?? {};
  const providers: string[] = Array.isArray(meta.providers) ? meta.providers : [meta.provider ?? ""];
  return { email: s.user.email ?? "", token: s.access_token, hasPassword: providers.includes("email") };
}

const origin = () => window.location.origin;

export function AuthProvider({ children }: { children: ReactNode }) {
  const isDev = config.authMode === "dev";
  // En el servidor no hay localStorage: `undefined` significa "todavía cargando".
  const devRaw = useSyncExternalStore(subscribeDev, getDevRaw, () => undefined);
  const devSession = useMemo(() => parseDev(devRaw), [devRaw]);
  const [sbSession, setSbSession] = useState<Session | null>(null);
  const [sbLoading, setSbLoading] = useState(!isDev);

  useEffect(() => {
    if (isDev) return;
    const sb = getSupabase();
    sb.auth.getSession().then(({ data }) => {
      setSbSession(fromSupabase(data.session));
      setSbLoading(false);
    });
    const { data } = sb.auth.onAuthStateChange((_event, s) => setSbSession(fromSupabase(s)));
    return () => data.subscription.unsubscribe();
  }, [isDev]);

  const session = isDev ? devSession : sbSession;
  const loading = isDev ? devRaw === undefined : sbLoading;

  const signIn = useCallback(async (email: string, password: string, captchaToken?: string) => {
    if (config.authMode === "dev") {
      const normalized = email.trim().toLowerCase();
      writeDevRaw(JSON.stringify({ email: normalized, token: `dev:${normalized}` }));
      return;
    }
    const { error } = await getSupabase().auth.signInWithPassword({ email, password, options: { captchaToken } });
    if (error) throw new Error(translateAuthError(error.message));
  }, []);

  const signUp = useCallback(
    async (email: string, password: string, captchaToken?: string) => {
      if (config.authMode === "dev") {
        await signIn(email, password);
        return { needsConfirmation: false };
      }
      const { data, error } = await getSupabase().auth.signUp({
        email,
        password,
        options: { emailRedirectTo: `${origin()}/dashboard`, captchaToken },
      });
      if (error) throw new Error(translateAuthError(error.message));
      return { needsConfirmation: !data.session };
    },
    [signIn],
  );

  const signInWithGoogle = useCallback(async () => {
    const { error } = await getSupabase().auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${origin()}/dashboard` },
    });
    if (error) throw new Error(translateAuthError(error.message));
  }, []);

  const requestPasswordReset = useCallback(async (email: string, captchaToken?: string) => {
    const { error } = await getSupabase().auth.resetPasswordForEmail(email, {
      redirectTo: `${origin()}/reset-password`,
      captchaToken,
    });
    if (error) throw new Error(translateAuthError(error.message));
  }, []);

  const updatePassword = useCallback(async (password: string) => {
    const { error } = await getSupabase().auth.updateUser({ password });
    if (error) throw new Error(translateAuthError(error.message));
  }, []);

  const updateEmail = useCallback(async (email: string) => {
    const { error } = await getSupabase().auth.updateUser({ email }, { emailRedirectTo: `${origin()}/account` });
    if (error) throw new Error(translateAuthError(error.message));
  }, []);

  const signOut = useCallback(async () => {
    if (config.authMode === "dev") {
      writeDevRaw(null);
      return;
    }
    await getSupabase().auth.signOut();
  }, []);

  // Supabase renueva el token por su cuenta; se pide en cada llamada para no usar uno caducado.
  const getToken = useCallback(async () => {
    if (config.authMode === "dev") return parseDev(getDevRaw())?.token ?? null;
    const { data } = await getSupabase().auth.getSession();
    return data.session?.access_token ?? null;
  }, []);

  const value = useMemo(
    () => ({
      session,
      loading,
      signIn,
      signUp,
      signInWithGoogle,
      requestPasswordReset,
      updatePassword,
      updateEmail,
      signOut,
      getToken,
    }),
    [session, loading, signIn, signUp, signInWithGoogle, requestPasswordReset, updatePassword, updateEmail, signOut, getToken],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return ctx;
}

function translateAuthError(message: string): string {
  const m = message.toLowerCase();
  if (m.includes("invalid login")) return "Email o contraseña incorrectos.";
  if (m.includes("already registered") || m.includes("already been registered")) {
    return "Ya existe una cuenta con ese email.";
  }
  if (m.includes("password should be") || m.includes("weak")) {
    return "La contraseña es demasiado débil: usa al menos 8 caracteres combinando letras y números.";
  }
  if (m.includes("different from the old")) return "La nueva contraseña debe ser distinta de la actual.";
  if (m.includes("email not confirmed")) return "Confirma tu email antes de entrar (revisa tu bandeja de entrada).";
  if (m.includes("captcha")) return "No hemos podido verificar que no eres un robot. Vuelve a intentarlo.";
  if (m.includes("rate limit") || m.includes("security purposes")) {
    return "Has hecho demasiados intentos seguidos. Espera un minuto y vuelve a probar.";
  }
  if (m.includes("reauthenticat")) return "Por seguridad, cierra sesión y vuelve a entrar antes de hacer este cambio.";
  if (m.includes("provider is not enabled")) return "El acceso con Google todavía no está disponible.";
  if (m.includes("invalid") && m.includes("email")) return "Ese email no es válido.";
  return "No se pudo completar la operación. Inténtalo de nuevo.";
}
