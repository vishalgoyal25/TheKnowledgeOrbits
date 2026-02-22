/**
 * Delete article confirmation dialog
 * TODO: Implement full dialog UI in upcoming phase
 */

"use client";

import { Button } from "@/components/ui/button";

interface Props {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  articleTitle: string;
  isDeleting: boolean;
}

export default function DeleteArticleDialog({
  open,
  onClose,
  onConfirm,
  articleTitle,
  isDeleting,
}: Props) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4 shadow-xl">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          Delete Article
        </h3>
        <p className="text-gray-600 mb-6">
          Are you sure you want to delete &quot;{articleTitle}&quot;? This
          action cannot be undone.
        </p>
        <div className="flex justify-end gap-3">
          <Button variant="outline" onClick={onClose} disabled={isDeleting}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={onConfirm}
            disabled={isDeleting}
          >
            {isDeleting ? "Deleting..." : "Delete"}
          </Button>
        </div>
      </div>
    </div>
  );
}
