/**
 * Edit bookmark notes dialog
 * TODO: Enhance with rich text in upcoming phase
 */

"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { bookmarksAPI } from "@/lib/api/bookmarks";

interface Props {
  open: boolean;
  onClose: () => void;
  bookmarkId: string;
  currentNotes: string;
  onSaved: () => void;
}

export default function EditNotesDialog({
  open,
  onClose,
  bookmarkId,
  currentNotes,
  onSaved,
}: Props) {
  const [notes, setNotes] = useState(currentNotes);
  const [isSaving, setIsSaving] = useState(false);

  if (!open) return null;

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await bookmarksAPI.updateNotes(bookmarkId, notes);
      onSaved();
      onClose();
    } catch (error) {
      console.error("Save notes failed:", error);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4 shadow-xl">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Edit Notes</h3>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          className="w-full border rounded-lg p-3 text-sm min-h-[120px] focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Add your notes here..."
        />
        <div className="flex justify-end gap-3 mt-4">
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? "Saving..." : "Save"}
          </Button>
        </div>
      </div>
    </div>
  );
}
