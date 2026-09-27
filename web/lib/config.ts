// Configuración pública del frontend (variables NEXT_PUBLIC_*, se incrustan en el bundle).

export const config = {
  apiUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  // "dev": login sin contraseña contra la API local. "supabase": Supabase Auth.
  authMode: (process.env.NEXT_PUBLIC_AUTH_MODE ?? "dev") as "dev" | "supabase",
  supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
  supabaseAnonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "",
} as const;
