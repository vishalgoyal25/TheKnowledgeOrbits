/**
 * Article listing page
 */

"use client";

import { useState } from "react";
import { useArticles } from "@/lib/hooks/use-article";
import ArticleCard from "@/components/articles/article-card";
import SearchBar from "@/components/search/search-bar";
import SearchFilters from "@/components/search/search-filters";
import ErrorMessage from "@/components/shared/error-message";
import EmptyState from "@/components/shared/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { Sparkles } from "lucide-react";

export default function ArticlesPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [activeFilters, setActiveFilters] = useState<string[]>([]);

  const filterOptions = [
    { label: "Approved", value: "approved" },
    { label: "Pending", value: "pending" },
    { label: "AI Generated", value: "ai_generated" },
  ];

  const filterStatus =
    activeFilters.find((f) => ["approved", "pending"].includes(f)) || "";

  const { data, isLoading, error } = useArticles({
    review_status: filterStatus || undefined,
    ordering: "-created_at",
  });

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-64" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <ErrorMessage
          title="Failed to load articles"
          message="Could not fetch articles. Please check your connection and try again."
          onRetry={() => window.location.reload()}
        />
      </div>
    );
  }

  const articles = data?.results || [];

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2">Articles</h1>
        <p className="text-gray-600">
          Browse AI-generated articles on UPSC topics
        </p>
      </div>

      {/* Search & Filters */}
      <div className="mb-6 space-y-3">
        <SearchBar
          placeholder="Search articles..."
          onSearch={setSearchTerm}
          defaultValue={searchTerm}
        />
        <SearchFilters
          filters={filterOptions}
          activeFilters={activeFilters}
          onFilterToggle={(val) =>
            setActiveFilters((prev) =>
              prev.includes(val)
                ? prev.filter((f) => f !== val)
                : [...prev, val],
            )
          }
          onClearAll={() => setActiveFilters([])}
          label="Filter"
        />
      </div>

      {/* Stats */}
      <div className="mb-6 text-sm text-gray-600">
        Showing {articles.length} of {data?.count || 0} articles
      </div>

      {/* Article Grid */}
      {articles.length === 0 ? (
        <EmptyState
          title="No articles found"
          description={
            searchTerm
              ? `No articles match "${searchTerm}". Try a different search.`
              : "No articles yet. Generate your first article to get started."
          }
          icon={<Sparkles className="h-8 w-8" />}
          action={
            !searchTerm ? (
              <Link href="/generate">
                <Button className="gap-2">
                  <Sparkles className="h-4 w-4" />
                  Generate Article
                </Button>
              </Link>
            ) : undefined
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {articles.map((article) => (
            <ArticleCard key={article.id} article={article} />
          ))}
        </div>
      )}
    </div>
  );
}
