"use client";

/**
 * Sends one GA4 page_view per route, including the first load — GoogleAnalytics.tsx
 * sets send_page_view: false, so this component owns every pageview.
 *
 * The default export is Suspense-wrapped on purpose. useSearchParams() opts a route
 * out of static rendering unless it sits inside a Suspense boundary, and this mounts
 * in the root layout — so an unwrapped mount would turn every page on the site
 * dynamic. Exporting it pre-wrapped makes that mistake impossible at the usage site.
 */
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
  }
}

function PageViewTrackerInner() {
  const pathname = usePathname();
  const query = useSearchParams().toString();

  useEffect(() => {
    if (typeof window.gtag !== "function") {
      return;
    }

    window.gtag("event", "page_view", {
      page_path: query ? `${pathname}?${query}` : pathname,
      page_location: window.location.href,
    });
  }, [pathname, query]);

  return null;
}

export default function PageViewTracker() {
  return (
    <Suspense fallback={null}>
      <PageViewTrackerInner />
    </Suspense>
  );
}
