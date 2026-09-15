import { absoluteUrl, SITE_NAME } from "@/lib/seo/site";

/**
 * JSON-LD structured data (G3.5). Inline in the HTML — no request, no
 * function invocation, a few hundred bytes. Server-rendered only, on pages
 * whose content is in the initial HTML; never on a client-fetched shell
 * (the markup would describe content the crawler cannot see — G0.1 decision).
 *
 * JSON.stringify escapes "<" so the payload cannot break out of the script
 * element even if a title contains one.
 */
function Script({ data }: { data: Record<string, unknown> }) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{
        __html: JSON.stringify(data).replace(/</g, "\\u003c"),
      }}
    />
  );
}

export function ArticleJsonLd({
  headline,
  description,
  path,
  datePublished,
  dateModified,
  section,
  image,
}: {
  headline: string;
  description: string;
  path: string;
  datePublished?: string;
  dateModified?: string;
  section?: string;
  image?: string | null;
}) {
  return (
    <Script
      data={{
        "@context": "https://schema.org",
        "@type": "Article",
        headline,
        description,
        mainEntityOfPage: absoluteUrl(path),
        url: absoluteUrl(path),
        ...(datePublished ? { datePublished } : {}),
        ...(dateModified ? { dateModified } : {}),
        ...(section ? { articleSection: section } : {}),
        ...(image ? { image: [image] } : {}),
        author: { "@type": "Organization", name: SITE_NAME },
        publisher: {
          "@type": "Organization",
          name: SITE_NAME,
          url: absoluteUrl("/"),
        },
        inLanguage: "en-IN",
        isAccessibleForFree: true,
      }}
    />
  );
}

export function BreadcrumbJsonLd({
  items,
}: {
  items: { name: string; path: string }[];
}) {
  return (
    <Script
      data={{
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        itemListElement: items.map((item, i) => ({
          "@type": "ListItem",
          position: i + 1,
          name: item.name,
          item: absoluteUrl(item.path),
        })),
      }}
    />
  );
}
