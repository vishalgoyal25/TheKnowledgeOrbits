"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getConceptDetail, ConceptDetail } from "@/lib/api/tags";
import { ConceptDetailComponent } from "@/components/concepts/concept-detail";

export default function ConceptPage() {
  const { slug } = useParams<{ slug: string }>();
  const router = useRouter();

  const [concept, setConcept] = useState<ConceptDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchConcept = useCallback(async () => {
    if (!slug) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getConceptDetail(slug);
      setConcept(data);
    } catch {
      setError("Concept not found.");
    } finally {
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    fetchConcept();
  }, [fetchConcept]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="bg-white border-b border-gray-200 px-4 py-7">
          <div className="max-w-[1200px] mx-auto space-y-2">
            <div className="h-4 bg-gray-200 rounded animate-pulse w-24" />
            <div className="h-7 bg-gray-200 rounded animate-pulse w-1/2" />
          </div>
        </div>
        <div className="max-w-[1200px] mx-auto px-4 py-6">
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
            <div className="space-y-4">
              <div className="h-32 bg-white rounded-2xl border border-gray-200 animate-pulse" />
              <div className="h-64 bg-white rounded-2xl border border-gray-200 animate-pulse" />
            </div>
            <div className="hidden lg:block h-48 bg-white rounded-xl border border-gray-200 animate-pulse" />
          </div>
        </div>
      </div>
    );
  }

  if (error || !concept) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-4xl mb-4">🔷</p>
          <p className="text-gray-700 font-semibold mb-2">
            {error ?? "Concept not found"}
          </p>
          <button
            onClick={() => router.push("/daily-ca")}
            className="text-sm text-blue-600 hover:underline"
          >
            ← Back to Daily CA
          </button>
        </div>
      </div>
    );
  }

  return <ConceptDetailComponent concept={concept} />;
}
