'use client';

import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Bookmark } from '@/types/notebook';
import { bookmarksAPI } from '@/lib/api/bookmarks';
import { FileText, Brain, Trash2, Edit, ExternalLink } from 'lucide-react';
import { useRouter } from 'next/navigation';
import RemoveBookmarkDialog from './RemoveBookmarkDialog';

interface Props {
  bookmark: Bookmark;
  onRemove: () => void;
}

export default function BookmarkCard({ bookmark, onRemove }: Props) {
  const router = useRouter();
  const [showRemoveDialog, setShowRemoveDialog] = useState(false);
  const [isRemoving, setIsRemoving] = useState(false);

  const handleRemove = async () => {
    setIsRemoving(true);
    try {
      await bookmarksAPI.removeBookmark(bookmark.id);
      onRemove();
      setShowRemoveDialog(false);
    } catch (error) {
      console.error('Remove failed:', error);
    } finally {
      setIsRemoving(false);
    }
  };

  const handleView = () => {
    if (bookmark.content_type === 'article') {
      router.push(`/articles/${bookmark.content_id}`);
    } else if (bookmark.content_type === 'quiz') {
      router.push(`/assessment/quiz/${bookmark.content_id}`);
    }
  };

  const icon = bookmark.content_type === 'article' 
    ? <FileText className="h-5 w-5 text-blue-600" />
    : <Brain className="h-5 w-5 text-green-600" />;

  return (
    <>
      <Card className="p-5 hover:shadow-lg transition-shadow">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              {icon}
              <span className="text-sm font-medium text-gray-500 uppercase">
                {bookmark.content_type}
              </span>
            </div>

            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              {bookmark.content?.title || 'Untitled'}
            </h3>

            {bookmark.notes && (
              <p className="text-sm text-gray-600 mb-3 italic">
                📝 {bookmark.notes}
              </p>
            )}

            <p className="text-xs text-gray-500">
              Bookmarked {new Date(bookmark.created_at).toLocaleDateString()}
            </p>
          </div>

          <div className="flex items-center gap-2 ml-4">
            <Button
              variant="outline"
              size="sm"
              onClick={handleView}
              className="flex items-center gap-1"
            >
              <ExternalLink className="h-4 w-4" />
              View
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowRemoveDialog(true)}
              className="text-red-600 hover:bg-red-50"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </Card>

      <RemoveBookmarkDialog
        open={showRemoveDialog}
        onClose={() => setShowRemoveDialog(false)}
        onConfirm={handleRemove}
        isRemoving={isRemoving}
      />
    </>
  );
}
