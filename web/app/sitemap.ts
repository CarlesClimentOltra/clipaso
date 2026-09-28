import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/seo";

export default function sitemap(): MetadataRoute.Sitemap {
  const languages = { es: `${SITE_URL}/`, en: `${SITE_URL}/en` };
  const legal = ["privacidad", "terminos", "cookies", "aviso-legal"].map((slug) => ({
    url: `${SITE_URL}/legal/${slug}`,
    changeFrequency: "yearly" as const,
    priority: 0.2,
  }));
  return [
    { url: `${SITE_URL}/`, changeFrequency: "weekly", priority: 1, alternates: { languages } },
    { url: `${SITE_URL}/en`, changeFrequency: "weekly", priority: 0.9, alternates: { languages } },
    { url: `${SITE_URL}/login`, changeFrequency: "yearly", priority: 0.3 },
    ...legal,
  ];
}
