/**
 * useInsights Hook - Fetch and manage AI-powered learning insights
 */

'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { analyticsAPI } from '../api/analytics';
import { Insight } from '@/types/dashboard';
import { toast } from '@/hooks/use-toast';

export function useInsights() {
    const queryClient = useQueryClient();

    // Query to fetch existing insights
    const query = useQuery<Insight[]>({
        queryKey: ['insights'],
        queryFn: async () => {
            const dashboard = await analyticsAPI.getDashboard();
            return dashboard.insights;
        },
        staleTime: 10 * 1000 * 60, // 10 minutes
    });

    // Mutation to trigger generation of new insights
    const generateMutation = useMutation({
        mutationFn: analyticsAPI.generateInsights,
        onSuccess: (newInsights) => {
            // Update the cache with new insights
            queryClient.setQueryData(['insights'], newInsights);
            toast({
                title: 'Insights Updated',
                description: 'AI has analyzed your recent performance.',
            });
        },
        onError: (error: any) => {
            toast({
                title: 'Analysis Failed',
                description: 'Failed to generate new insights. Please try again later.',
                variant: 'destructive',
            });
        }
    });

    return {
        ...query,
        generateInsights: generateMutation.mutate,
        isGenerating: generateMutation.isPending,
    };
}
