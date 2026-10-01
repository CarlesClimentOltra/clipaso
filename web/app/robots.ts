import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/seo";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      // Zona privada de la app: no aporta nada a los buscadores.
      disallow: ["/dashboard", "/new", "/projects", "/account", "/customize", "/plans", "/admin", "/reset-password"],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
