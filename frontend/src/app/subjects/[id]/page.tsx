import { subjectsAPI } from "@/lib/api/subjects";
import { BookOpen } from "lucide-react";
import ModuleCard from "@/components/modules/module-card";
import { Module, Subject } from "@/lib/types";

export const revalidate = 3600;

export default async function SubjectPage(props: {
  params: Promise<{ id: string }>;
}) {
  const params = await props.params;
  const subjectId = params.id;
  let subject: Subject | null = null;
  let modules: Module[] = [];

  try {
    subject = await subjectsAPI.getById(subjectId);
    modules = await subjectsAPI.getModulesBySubject(subjectId) as Module[];
  } catch (error) {
    if (process.env.SKIP_BACKEND_WAIT !== "true") {
      console.error(`Failed to fetch subject details: ${error}`);
    }
  }

  if (!subject) {
    return (
      <div className="container mx-auto px-4 py-16 text-center text-slate-500">
        <h1 className="text-3xl font-black uppercase tracking-tight text-slate-300">Subject Not Found</h1>
        <p className="mt-4">The subject you are explicitly looking for does not uniquely exist.</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      {/* Header */}
      <div className="mb-10 pb-6 border-b border-slate-100">
        <div className="flex items-center gap-3 text-blue-600 mb-3">
          <BookOpen className="h-10 w-10" />
          <h1 className="text-4xl md:text-5xl font-black font-heading tracking-tighter text-slate-900">
            {subject.name}
          </h1>
        </div>
        <p className="text-slate-600 text-lg md:text-xl font-medium max-w-3xl">
          {subject.description || "Browse interconnected modules mapped within this core subject."}
        </p>
      </div>

      {/* Grid Layout */}
      {modules.length === 0 ? (
        <div className="text-center py-20 bg-slate-50 rounded-2xl border border-dashed border-slate-200">
          <p className="text-slate-500 font-medium">No modules available for this subject yet.</p>
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
