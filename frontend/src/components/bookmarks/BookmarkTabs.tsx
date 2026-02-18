/**
 * Bookmark tabs — filter bookmarks by type (all, articles, quizzes)
 * TODO: Enhance with counts and animations in upcoming phase
 */

'use client';

interface Props {
    activeTab: 'all' | 'article' | 'quiz';
    onTabChange: (tab: 'all' | 'article' | 'quiz') => void;
}

export default function BookmarkTabs({ activeTab, onTabChange }: Props) {
    const tabs = [
        { value: 'all' as const, label: 'All' },
        { value: 'article' as const, label: 'Articles' },
        { value: 'quiz' as const, label: 'Quizzes' },
    ];

    return (
        <div className="flex gap-2 mb-4">
            {tabs.map(tab => (
                <button
                    key={tab.value}
                    onClick={() => onTabChange(tab.value)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === tab.value
                            ? 'bg-blue-600 text-white'
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                        }`}
                >
                    {tab.label}
                </button>
            ))}
        </div>
    );
}
