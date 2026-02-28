"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Article } from "@/types/notebook";
import { notebookAPI } from "@/lib/api/notebook";
import { FileText, Calendar, Clock, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import DeleteArticleDialog from "./DeleteArticleDialog";
import { createLogger } from "@/lib/logger";

const logger = createLogger("Notebook");

interface Props {
  article: Article;
  onDelete: () => void;
}

export default function ArticleCard({ article, onDelete }: Props) {
  const router = useRouter();
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await notebookAPI.deleteArticle(article.id);
      onDelete();
      setShowDeleteDialog(false);
    } catch (error) {
      logger.error("Delete failed:", error);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <>
      <Card
        className="p-6 hover:shadow-lg transition-shadow cursor-pointer"
        onClick={() => router.push(`/articles/${article.id}`)}
      >
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <FileText className="h-5 w-5 text-blue-600" />
              <h3 className="text-xl font-semibold text-gray-900">
                {article.title}
              </h3>
            </div>

            <p className="text-gray-600 text-sm mb-4 line-clamp-2">
              {article.summary}
            </p>

            <div className="flex items-center gap-4 text-sm text-gray-500">
              <span className="flex items-center gap-1">
                <Calendar className="h-4 w-4" />
                {new Date(article.created_at).toLocaleDateString()}
              </span>
              <span className="flex items-center gap-1">
                <Clock className="h-4 w-4" />
                {article.read_time} min read
              </span>
              <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">
                {article.topic.name}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 ml-4">
            <Button
              variant="outline"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                setShowDeleteDialog(true);
              }}
              className="text-red-600 hover:bg-red-50"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </Card>

      <DeleteArticleDialog
        open={showDeleteDialog}
        onClose={() => setShowDeleteDialog(false)}
        onConfirm={handleDelete}
        articleTitle={article.title}
        isDeleting={isDeleting}
      />
    </>
  );
}
