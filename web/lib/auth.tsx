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
import { dictionary } from "@/lib/i18n";
import { getLocale } from "@/lib/i18n/store";

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

const DEV_KEY = "clipaso.dev-session";
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
        options: { emailRedirectTo: `${origin()}/dashboard`, captchaToken, data: { locale: getLocale() } },
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
  const t = dictionary().auth;
  if (m.includes("invalid login")) return t.invalidLogin;
  if (m.includes("already registered") || m.includes("already been registered")) return t.alreadyRegistered;
  if (m.includes("password should be") || m.includes("weak")) return t.weakPassword;
  if (m.includes("different from the old")) return t.samePassword;
  if (m.includes("email not confirmed")) return t.emailNotConfirmed;
  if (m.includes("captcha")) return t.captcha;
  if (m.includes("rate limit") || m.includes("security purposes")) return t.rateLimit;
  if (m.includes("reauthenticat")) return t.reauth;
  if (m.includes("provider is not enabled")) return t.googleDisabled;
  if (m.includes("invalid") && m.includes("email")) return t.invalidEmail;
  return t.generic;
}
