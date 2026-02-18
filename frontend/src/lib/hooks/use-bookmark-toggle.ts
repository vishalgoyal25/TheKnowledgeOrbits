'use client';

import { useState, useEffect } from 'react';
import { bookmarksAPI } from '@/lib/api/bookmarks';
import { useQueryClient } from '@tanstack/react-query';
import { tokenManager } from '@/lib/auth/token-manager';

export function useBookmarkToggle(contentType: 'article' | 'quiz', contentId: string) {
    const [isBookmarked, setIsBookmarked] = useState(false);
    const [bookmarkId, setBookmarkId] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const queryClient = useQueryClient();

    // Check if bookmarked
    useEffect(() => {
        const checkBookmark = async () => {
            if (!tokenManager.getAccessToken()) return;
            try {
                const bookmarks = await bookmarksAPI.getBookmarks(contentType);
                const existing = bookmarks.find(b => b.content_id === contentId);
                if (existing) {
                    setIsBookmarked(true);
                    setBookmarkId(existing.id);
                }
            } catch (error) {
                console.error('Failed to check bookmark:', error);
            }
        };
        checkBookmark();
    }, [contentType, contentId]);

    const toggle = async () => {
        if (!tokenManager.getAccessToken()) {
            window.location.href = '/auth/login';
            return;
        }
        setIsLoading(true);
        try {
            if (isBookmarked && bookmarkId) {
                // Remove bookmark
                await bookmarksAPI.removeBookmark(bookmarkId);
                setIsBookmarked(false);
                setBookmarkId(null);
            } else {
                // Add bookmark
                const bookmark = await bookmarksAPI.addBookmark({
                    content_type: contentType,
                    content_id: contentId,
                });
                setIsBookmarked(true);
                setBookmarkId(bookmark.id);
            }

            // Invalidate bookmarks cache
            queryClient.invalidateQueries({ queryKey: ['bookmarks'] });
        } catch (error) {
            console.error('Bookmark toggle failed:', error);
        } finally {
            setIsLoading(false);
        }
    };

    return { isBookmarked, toggle, isLoading };
}
