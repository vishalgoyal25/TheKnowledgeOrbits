'use client';

import { useQuery } from '@tanstack/react-query';
import { bookmarksAPI } from '@/lib/api/bookmarks';

export function useBookmarks(contentType?: 'article' | 'quiz') {
  return useQuery({
    queryKey: ['bookmarks', contentType],
    queryFn: () => bookmarksAPI.getBookmarks(contentType),
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}
