import { subjectsAPI } from "@/lib/api/subjects";
import { topicsAPI } from "@/lib/api/topics";
import { Layers } from "lucide-react";
import TopicCard from "@/components/topics/topic-card";
import { Topic, Module } from "@/lib/types";

export const revalidate = 3600;

export default async function ModulePage(props: {
  params: Promise<{ id: string }>;
}) {
  const params = await props.params;
  const moduleId = params.id;
  let moduleData: Module | null = null;
  let topics: Topic[] = [];

  try {
    moduleData = await subjectsAPI.getModuleById(moduleId);
    topics = await topicsAPI.listByModule(moduleId, { page_size: 200 }) as Topic[];
  } catch (error) {
    if (process.env.SKIP_BACKEND_WAIT !== "true") {
      console.error("Failed to fetch module details", error);
    }
  }

  if (!moduleData) {
    return (
      <div className="container mx-auto px-4 py-16 text-center text-slate-500">
        <h1 className="text-3xl font-black uppercase tracking-tight text-slate-300">Module Not Found</h1>
        <p className="mt-4">The module mapping you're trying to view doesn't exist.</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      {/* Header */}
      <div className="mb-10 pb-6 border-b border-slate-100">
        <div className="flex items-center gap-3 text-emerald-600 mb-3">
          <Layers className="h-10 w-10" />
          <h1 className="text-4xl md:text-5xl font-black font-heading tracking-tighter text-slate-900">
            {moduleData.name}
          </h1>
        </div>
        <p className="text-slate-600 text-lg md:text-xl font-medium max-w-3xl">
          {moduleData.description || "Deep dive into the specific syllabus topics contained within this module."}
        </p>
      </div>

      {/* Grid Layout */}
      {topics.length === 0 ? (
        <div className="text-center py-20 bg-slate-50 rounded-2xl border border-dashed border-slate-200">
          <p className="text-slate-500 font-medium">No topics mapped to this specific module yet.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {topics.map((topic) => (
            <TopicCard key={topic.id} topic={topic} />
          ))}
        </div>
      )}
    </div>
  );
}
