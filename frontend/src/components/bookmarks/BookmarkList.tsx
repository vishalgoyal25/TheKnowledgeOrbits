/**
 * Bookmark list — renders a list of bookmark cards
 * TODO: Enhance with pagination/virtualization in upcoming phase
 */

'use client';

import { Bookmark } from '@/types/notebook';
import BookmarkCard from './BookmarkCard';

interface Props {
    bookmarks: Bookmark[];
    onRemove: () => void;
}

export default function BookmarkList({ bookmarks, onRemove }: Props) {
    return (
        <div className="space-y-4">
            {bookmarks.map(bookmark => (
                <BookmarkCard key={bookmark.id} bookmark={bookmark} onRemove={onRemove} />
            ))}
        </div>
    );
}
