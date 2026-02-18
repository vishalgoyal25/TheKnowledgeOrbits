'use client';

import { useState, useCallback, useEffect } from 'react';
import apiClient from '@/lib/api/client';
import { debounce } from 'lodash';

interface ReadingProgress {
    percent_read: number;
    last_position: number;
}

export function useReadingProgress(articleId: string) {
    const [progress, setProgress] = useState<ReadingProgress | null>(null);

    // Load saved progress
    useEffect(() => {
        const loadProgress = async () => {
            try {
                const response = await apiClient.get(`/userstate/reading-progress/${articleId}/`);
                setProgress(response.data);
            } catch (error) {
                // No saved progress or error
                setProgress({ percent_read: 0, last_position: 0 });
            }
        };
        loadProgress();
    }, [articleId]);

    // Debounced API call to save progress
    // eslint-disable-next-line react-hooks/exhaustive-deps
    const saveProgressDebounced = useCallback(
        debounce(async (percent: number, position: number) => {
            try {
                await apiClient.put(`/userstate/reading-progress/${articleId}/update/`, {
                    percent_read: percent,
                    last_position: position,
                });
            } catch (error) {
                console.error('Failed to save reading progress:', error);
            }
        }, 1000),
        [articleId]
    );

    // Immediate UI update + debounced save
    const updateProgress = useCallback(
        (percent: number, position: number) => {
            setProgress({ percent_read: percent, last_position: position });
            saveProgressDebounced(percent, position);
        },
        [saveProgressDebounced]
    );

    return { progress, updateProgress };
}
