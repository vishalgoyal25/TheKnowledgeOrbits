import Link from "next/link";
import { ChevronRight, Home } from "lucide-react";

import type { Crumb } from "@/lib/syllabus-tree";
import { modulePath, subjectPath, topicPath } from "@/lib/content-urls";

/**
 * Server-renderable breadcrumb for the hierarchy pages (G3.13):
 *   Home › Syllabus › Subject › Module › Topic › … › current
 * The trail comes from `trailTo()`; position decides the route each crumb links
 * to (index 0 = subject, 1 = module, 2+ = topics). The last crumb is the page
 * itself and is not a link. Google reads this as the page's place in the site;
 * `BreadcrumbList` JSON-LD (G3.5) will mirror it.
 */
export default function SyllabusBreadcrumb({ trail }: { trail: Crumb[] }) {
  const last = trail.length - 1;
  const hrefFor = (crumb: Crumb, i: number) =>
    i === 0
      ? subjectPath(crumb)
      : i === 1
        ? modulePath(crumb)
        : topicPath(crumb);

  return (
    <nav aria-label="Breadcrumb" className="mb-6 overflow-x-auto">
      <ol className="flex items-center gap-1.5 text-sm text-muted-foreground whitespace-nowrap">
        <li className="flex items-center gap-1.5">
          <Link href="/" className="flex items-center gap-1 hover:text-primary">
            <Home className="h-3.5 w-3.5" />
            Home
          </Link>
        </li>
        <li className="flex items-center gap-1.5">
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/50" />
          <Link href="/subjects" className="hover:text-primary">
            Syllabus
          </Link>
        </li>
        {trail.map((crumb, i) => (
          <li key={crumb.id} className="flex items-center gap-1.5">
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/50" />
            {i === last ? (
              <span className="font-medium text-foreground" aria-current="page">
                {crumb.name}
              </span>
            ) : (
              <Link href={hrefFor(crumb, i)} className="hover:text-primary">
                {crumb.name}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
