/**
 * Article Skeleton - Loading state for the article reader
 */

import React from 'react';
import { Skeleton } from '@/components/ui/skeleton';

export default function ArticleSkeleton() {
    return (
        <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in duration-500">
            {/* Title & Metadata Skeleton */}
            <div className="space-y-4">
                <Skeleton className="h-12 w-3/4" />
                <div className="flex gap-4">
                    <Skeleton className="h-5 w-24" />
                    <Skeleton className="h-5 w-32" />
                    <Skeleton className="h-5 w-20" />
                </div>
            </div>

            {/* Hero Image Skeleton (Optional placeholder) */}
            <Skeleton className="h-[300px] w-full rounded-2xl" />

            {/* Content Skeleton */}
            <div className="space-y-6">
                <div className="space-y-2">
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-5/6" />
                </div>

                <div className="space-y-2">
                    <Skeleton className="h-6 w-1/4 mt-8" />
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-4/5" />
                </div>

                <div className="space-y-2">
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-3/4" />
                </div>
            </div>

            {/* Sidebar/Source Placeholder */}
            <div className="pt-12 border-t">
                <Skeleton className="h-8 w-48 mb-6" />
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Skeleton className="h-32 w-full" />
                    <Skeleton className="h-32 w-full" />
                </div>
            </div>
        </div>
    );
}
