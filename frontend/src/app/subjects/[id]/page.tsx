import { subjectsAPI } from "@/lib/api/subjects";
import { BookOpen } from "lucide-react";
import { permanentRedirect } from "next/navigation";
import ModuleCard from "@/components/modules/module-card";
import { Module, Subject } from "@/lib/types";
import { isUuid, subjectPath } from "@/lib/content-urls";

// Revalidate daily — syllabus subjects rarely change; hourly rebuilds across
// many dynamic pages wasted Vercel ISR-write quota.
export const revalidate = 86400;

export default async function SubjectPage(props: {
  params: Promise<{ id: string }>;
}) {
  const params = await props.params;
  // Slug or UUID (G3.10) — the API resolves either; the module filter needs
  // the UUID, so it follows the subject fetch.
  const segment = params.id;
  let subject: Subject | null = null;
  let modules: Module[] = [];

  try {
    subject = await subjectsAPI.getById(segment);
    if (subject) {
      modules = (await subjectsAPI.getModulesBySubject(subject.id)) as Module[];
    }
  } catch (error) {
    if (process.env.SKIP_BACKEND_WAIT !== "true") {
      console.error(`Failed to fetch subject details: ${error}`);
    }
  }

  // Legacy UUID address → canonical slug address (308). Outside the try so
  // the redirect throw is never mistaken for a fetch failure.
  if (subject && isUuid(segment) && subject.slug) {
    permanentRedirect(subjectPath(subject));
  }

  if (!subject) {
    return (
      <div className="container mx-auto px-4 py-16 text-center text-muted-foreground">
        <h1 className="text-3xl font-semibold uppercase tracking-tight text-muted-foreground">
          Subject Not Found
        </h1>
        <p className="mt-4">
          The subject you are explicitly looking for does not uniquely exist.
        </p>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      {/* Header */}
      <div className="mb-10 pb-6 border-b border-border">
        <div className="flex items-center gap-3 text-blue-600 mb-3">
          <BookOpen className="h-10 w-10" />
          <h1 className="text-4xl md:text-5xl font-semibold font-heading tracking-tighter text-foreground">
            {subject.name}
          </h1>
        </div>
        <p className="text-muted-foreground text-lg md:text-xl font-medium max-w-3xl">
          {subject.description ||
            "Browse interconnected modules mapped within this core subject."}
        </p>
      </div>

      {/* Grid Layout */}
      {modules.length === 0 ? (
        <div className="text-center py-20 bg-muted/40 rounded-lg border border-dashed border-border">
          <p className="text-muted-foreground font-medium">
            No modules available for this subject yet.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {modules.map((module) => (
            <ModuleCard key={module.id} module={module} />
          ))}
        </div>
      )}
    </div>
  );
}
