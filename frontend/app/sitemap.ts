import type { MetadataRoute } from "next";
import { LANES } from "@/lib/lanes";
import { SITE_URL } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  return [
    { url: `${SITE_URL}/`, lastModified: now, priority: 1 },
    { url: `${SITE_URL}/shipping`, lastModified: now, priority: 0.8 },
    { url: `${SITE_URL}/tools/cbm-calculator`, lastModified: now, priority: 0.7 },
    // Only reviewed lane pages are submitted for indexing.
    ...LANES.filter((l) => l.reviewed).map((l) => ({ url: `${SITE_URL}/shipping/${l.slug}`, lastModified: now, priority: 0.9 })),
  ];
}
