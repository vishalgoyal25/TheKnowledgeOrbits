import KnowledgeMapPage from "@/components/book-content/knowledge-map-page";

/**
 * /knowledge — Knowledge Map, no selection yet.
 *
 * Static shell. The component canonicalises the address bar to
 * /knowledge/<default-subject> once subjects load; selections push
 * /knowledge/<subject>/<topic>, which /knowledge/[...path] serves on refresh.
 */

export const metadata = {
  title: "Knowledge Map — TheKnowledgeOrbits",
  description:
    "Browse the UPSC syllabus as a connected map — every subject, module and topic, with AI-generated articles one click away.",
};

export default function KnowledgePage() {
  return <KnowledgeMapPage />;
}
