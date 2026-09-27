// Datos que aparecen en las páginas legales. Cambiar aquí si cambia el titular, el dominio o un proveedor.

export const legal = {
  updatedAt: "27 de septiembre de 2026",
  owner: {
    name: "Carles Climent Oltra",
    taxId: "20496132G", // NIF
    address: "Calle Cervantes, 3, Llocnou d'En Fenollet (Valencia), España",
    email: "carlesco03@gmail.com",
  },
  site: "smartcuts-kohl.vercel.app",
  minAge: 18,
  // Encargados del tratamiento (proveedores que tratan datos por cuenta de SmartCuts).
  processors: [
    {
      name: "Supabase",
      role: "Base de datos y cuentas de usuario (email y contraseña cifrada)",
      location: "Servidores en Frankfurt (UE)",
      company: "Supabase Inc. (EE. UU.)",
    },
    {
      name: "Cloudflare R2",
      role: "Almacenamiento de los vídeos subidos, clips y miniaturas",
      location: "Jurisdicción UE: los datos se guardan en la UE",
      company: "Cloudflare, Inc. (EE. UU.)",
    },
    {
      name: "Modal",
      role: "Procesamiento de los vídeos (transcripción, reencuadre y subtítulos) en servidores con GPU",
      location: "Servidores en la UE",
      company: "Modal Labs, Inc. (EE. UU.)",
    },
    {
      name: "Anthropic",
      role: "Selección de los mejores momentos con IA (Claude). Recibe el texto transcrito, no el vídeo",
      location: "EE. UU.",
      company: "Anthropic, PBC (EE. UU.)",
    },
    {
      name: "Fly.io",
      role: "Servidor de la aplicación (API)",
      location: "Servidores en Frankfurt (UE)",
      company: "Fly.io, Inc. (EE. UU.)",
    },
    {
      name: "Vercel",
      role: "Alojamiento de la web",
      location: "Red global; funciones en Frankfurt (UE)",
      company: "Vercel Inc. (EE. UU.)",
    },
    {
      name: "Brevo",
      role: "Envío de emails (confirmación de cuenta y avisos de tus vídeos)",
      location: "UE",
      company: "Sendinblue SAS (Francia)",
    },
    {
      name: "Cloudflare Turnstile",
      role: "Comprobación anti-bots en los formularios de acceso (sin cookies de seguimiento)",
      location: "Red global de Cloudflare",
      company: "Cloudflare, Inc. (EE. UU.)",
    },
    {
      name: "Sentry",
      role: "Registro de errores técnicos, sin datos personales identificativos",
      location: "Servidores en la UE",
      company: "Functional Software, Inc. (EE. UU.)",
    },
  ],
} as const;
