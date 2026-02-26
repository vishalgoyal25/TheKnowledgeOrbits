/**
 * Related articles recommendations
 * TODO: Implement ML-based recommendations in upcoming phase
 */

"use client";

interface Props {
  currentArticleId: string;
  topicId: string;
}

export default function RelatedArticles({
  currentArticleId: _currentArticleId,
  topicId: _topicId,
}: Props) {
  // TODO: Fetch related articles from API based on topic
  return (
    <div className="mt-12 pt-8 border-t">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Related Articles
      </h3>
      <p className="text-gray-500 text-sm">
        Related articles will appear here based on your reading history.
      </p>
    </div>
  );
}
