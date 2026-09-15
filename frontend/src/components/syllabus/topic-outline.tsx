import Link from "next/link";
import { BookOpen, ChevronRight, CircleDashed } from "lucide-react";

import type { TreeTopic } from "@/types/book-content";
import { topicPath } from "@/lib/content-urls";
import { cn } from "@/lib/utils";

/**
 * Nested, server-renderable list of topics → subtopics → sub-subtopics for the
 * hierarchy pages (G3.13). Replaces the flat card grid that showed every depth
 * as a peer and counted the wrong article table ("0 articles").
 *
 * Every row links to /topics/<slug> — the page that IS the article — and shows
 * whether that article exists yet, keyed on `has_content` (G2.7).
 */
export default function TopicOutline({
  topics,
  depth = 0,
}: {
  topics: TreeTopic[];
  depth?: number;
}) {
  if (topics.length === 0) return null;
  return (
    <ul className={cn(depth > 0 && "ml-5 border-l border-border pl-4 mt-1")}>
      {topics.map((t) => (
        <li key={t.id} className="py-1">
          <Link
            href={topicPath(t)}
            className={cn(
              "group flex items-center gap-2 rounded-md px-2 py-1.5 transition-colors hover:bg-muted/60",
              depth === 0
                ? "font-medium text-foreground"
                : "text-foreground/85",
            )}
          >
            {t.has_content ? (
              <BookOpen
                className="h-4 w-4 flex-shrink-0 text-green-600"
                aria-label="Article ready"
              />
            ) : (
              <CircleDashed
                className="h-4 w-4 flex-shrink-0 text-muted-foreground/50"
                aria-label="Article not yet generated"
              />
            )}
            <span className="flex-1 group-hover:text-primary">{t.name}</span>
            {t.subtopics.length > 0 && (
              <span className="text-[11px] text-muted-foreground">
                {t.subtopics.length}
              </span>
            )}
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/40 group-hover:text-primary" />
          </Link>
          <TopicOutline topics={t.subtopics} depth={depth + 1} />
        </li>
      ))}
    </ul>
  );
}
