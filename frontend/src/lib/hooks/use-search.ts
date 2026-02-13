/**
 * React Query hooks for search
 */

'use client';

import { useQuery } from '@tanstack/react-query';
import { searchAPI, SearchParams } from '../api/search';

export function useSearch(params: SearchParams, enabled: boolean = true) {
  return useQuery({
    queryKey: ['search', params],
    queryFn: () => searchAPI.search(params),
    enabled: enabled && !!params.q && params.q.length >= 2,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}
