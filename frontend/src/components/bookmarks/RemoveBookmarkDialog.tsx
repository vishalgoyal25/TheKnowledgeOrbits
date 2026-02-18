/**
 * Remove bookmark confirmation dialog
 * TODO: Enhance with animation in upcoming phase
 */

'use client';

import { Button } from '@/components/ui/button';

interface Props {
    open: boolean;
    onClose: () => void;
    onConfirm: () => void;
    isRemoving: boolean;
}

export default function RemoveBookmarkDialog({ open, onClose, onConfirm, isRemoving }: Props) {
    if (!open) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4 shadow-xl">
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Remove Bookmark</h3>
                <p className="text-gray-600 mb-6">
                    Are you sure you want to remove this bookmark?
                </p>
                <div className="flex justify-end gap-3">
                    <Button variant="outline" onClick={onClose} disabled={isRemoving}>
                        Cancel
                    </Button>
                    <Button
                        variant="destructive"
                        onClick={onConfirm}
                        disabled={isRemoving}
                    >
                        {isRemoving ? 'Removing...' : 'Remove'}
                    </Button>
                </div>
            </div>
        </div>
    );
}
