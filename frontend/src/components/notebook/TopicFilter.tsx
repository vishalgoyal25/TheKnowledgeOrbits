/**
 * Topic filter dropdown for notebook
 * TODO: Enhance with multi-select and API-driven topics in upcoming phase
 */

'use client';

import { Topic } from '@/types/notebook';

interface Props {
    topics: Topic[];
    selectedTopicId: string | null;
    onSelect: (topicId: string | null) => void;
}

export default function TopicFilter({ topics, selectedTopicId, onSelect }: Props) {
    return (
        <select
            value={selectedTopicId || ''}
            onChange={(e) => onSelect(e.target.value || null)}
            className="border rounded-lg px-3 py-2 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
            <option value="">All Topics</option>
            {topics.map(topic => (
                <option key={topic.id} value={topic.id}>
                    {topic.name}
                </option>
            ))}
        </select>
    );
}
