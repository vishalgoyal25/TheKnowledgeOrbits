/**
 * Hierarchical topic tree navigation
 */

'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Topic } from '@/lib/types';
import { ChevronRight, ChevronDown, FileText, Folder } from 'lucide-react';
import { cn } from '@/lib/utils';

interface TopicTreeProps {
    topics: Topic[];
}

interface TopicNodeProps {
    topic: Topic;
    level: number;
    articleCount?: number;
}

function TopicNode({ topic, level, articleCount = 0 }: TopicNodeProps) {
    const [isExpanded, setIsExpanded] = useState(level === 0);
    const hasChildren = false; // Topics don't have children in current schema

    return (
        <div className={cn('border-l border-gray-200', level > 0 && 'ml-4')}>
            <div
                className={cn(
                    'flex items-center gap-2 px-3 py-2 hover:bg-gray-50 cursor-pointer rounded-md transition-colors',
                    level === 0 && 'font-medium'
                )}
                onClick={() => setIsExpanded(!isExpanded)}
            >
                {hasChildren ? (
                    isExpanded ? (
                        <ChevronDown className="h-4 w-4 text-gray-500" />
                    ) : (
                        <ChevronRight className="h-4 w-4 text-gray-500" />
                    )
                ) : (
                    <div className="w-4" />
                )}

                <Folder className="h-4 w-4 text-blue-500" />

                <Link
                    href={`/topics/${topic.id}/articles`}
                    className="flex-1 hover:text-blue-600 transition-colors"
                    onClick={(e) => e.stopPropagation()}
                >
                    {topic.name}
                </Link>

                <div className="flex items-center gap-1 text-xs text-gray-500">
                    <FileText className="h-3 w-3" />
                    <span>{articleCount}</span>
                </div>
            </div>
        </div>
    );
}

export default function TopicTree({ topics }: TopicTreeProps) {
    // Group topics by module
    const moduleGroups = topics.reduce((acc, topic) => {
        const moduleName = topic.module_name;
        if (!acc[moduleName]) {
            acc[moduleName] = [];
        }
        acc[moduleName].push(topic);
        return acc;
    }, {} as Record<string, Topic[]>);

    return (
        <div className="space-y-2">
            {Object.entries(moduleGroups).map(([moduleName, moduleTopics]) => (
                <div key={moduleName} className="border rounded-lg p-2">
                    <div className="font-semibold text-sm text-gray-700 mb-2 px-2">
                        {moduleName}
                    </div>

                    {moduleTopics.map((topic) => (
                        <TopicNode key={topic.id} topic={topic} level={0} />
                    ))}
                </div>
            ))}
        </div>
    );
}
