import { useQuery } from "@tanstack/react-query";
import apiClient from "@/lib/api/client";
import { Article } from "@/lib/types";

interface ChunkResponse {
  results: {
    id: string;
    chunk_index: number;
    chunk_text: string;
    document: string; // document id
    chapter_name?: string;
    page_number?: number;
  }[];
}

interface DocumentResponse {
  id: string;
  title: string;
  description?: string;
  source_type: string;
  created_at: string;
}

// Fetch a document and its chunks to mimic an Article
export function useDocumentAsArticle(
  documentId: string,
  chunkIndexStr?: string | null,
  options?: { enabled?: boolean },
) {
  const chunkIndex = chunkIndexStr ? parseInt(chunkIndexStr) : 0;

  return useQuery({
    queryKey: ["document", documentId, chunkIndex],
    queryFn: async (): Promise<Article> => {
      // 1. Fetch Document Metadata
      const docRes = await apiClient.get<DocumentResponse>(
        `/content/documents/${documentId}/`,
      );
      const doc = docRes.data;

      const chunksRes = await apiClient.get<ChunkResponse>(`/content/chunks/`, {
        params: {
          document: documentId,
          limit: 20,
          start_index: Math.max(0, chunkIndex - 1),
          include_content: "true",
        },
      });

      // Construct content from chunks - Format as continuous text
      const chunks = chunksRes.data.results || [];
      // Sort by index just in case
      chunks.sort((a, b) => a.chunk_index - b.chunk_index);

      const content = chunks.map((c) => c.chunk_text).join("\n\n");

      return {
        id: doc.id,
        title: doc.title,
        content: content || "No content available for this section.",
        summary: doc.description || "Document content",
        html_content: null,
        topic: null,
        word_count: content.split(/\s+/).length,
        difficulty_level: "intermediate",
        reading_time_minutes: Math.ceil(content.split(/\s+/).length / 200),
        source_type: doc.source_type,
        published_at: doc.created_at,
        created_at: doc.created_at,
        updated_at: doc.created_at,
        author: {
          id: "system",
          username: "System",
          full_name: "Knowledge Base",
          avatar_url: null,
        },
        tags: [],
        references: [],
        generation_type: "static_document",
        is_public: true,
        is_bookmarked: false,
        user_preference: null,

        // Mock fields
        quality_score: 100,
        review_status: "approved",
        generation_metadata: {},
        source_chunks: [],
        static_chunk_count: chunks.length,
        ca_chunk_count: 0,
        source_chunk_count: chunks.length,

        // Missing fields
        slug: doc.title.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
        read_time: Math.ceil(content.split(/\s+/).length / 200).toString(),
        is_published: true,
      } as unknown as Article;
    },
    enabled: !!documentId && (options?.enabled ?? true),
    staleTime: 5 * 60 * 1000,
  });
}
