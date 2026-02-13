/**
 * React Query hooks for subjects and modules
 */

'use client';

import { useQuery } from '@tanstack/react-query';
import { subjectsAPI } from '../api/subjects';

export function useSubjects() {
  return useQuery({
    queryKey: ['subjects'],
    queryFn: () => subjectsAPI.list(),
    staleTime: 15 * 60 * 1000, // 15 minutes
  });
}

export function useSubject(id: string | null) {
  return useQuery({
    queryKey: ['subject', id],
    queryFn: () => subjectsAPI.getById(id!),
    enabled: !!id,
    staleTime: 15 * 60 * 1000,
  });
}

export function useModulesBySubject(subjectId: string | null) {
  return useQuery({
    queryKey: ['modules', 'subject', subjectId],
    queryFn: () => subjectsAPI.getModulesBySubject(subjectId!),
    enabled: !!subjectId,
    staleTime: 15 * 60 * 1000,
  });
}
