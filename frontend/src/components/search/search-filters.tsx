'use client';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { X, SlidersHorizontal } from 'lucide-react';

export interface FilterOption {
    label: string;
    value: string;
}

interface SearchFiltersProps {
    filters: FilterOption[];
    activeFilters: string[];
    onFilterToggle: (value: string) => void;
    onClearAll: () => void;
    label?: string;
}

export default function SearchFilters({
    filters,
    activeFilters,
    onFilterToggle,
    onClearAll,
    label = 'Filter by',
}: SearchFiltersProps) {
    if (!filters || filters.length === 0) return null;

    return (
        <div className="flex flex-wrap items-center gap-2">
            <span className="flex items-center gap-1.5 text-sm text-gray-500 font-medium">
                <SlidersHorizontal className="h-4 w-4" />
                {label}:
            </span>

            {filters.map((filter) => {
                const isActive = activeFilters.includes(filter.value);
                return (
                    <Badge
                        key={filter.value}
                        variant={isActive ? 'default' : 'outline'}
                        className={`cursor-pointer select-none transition-colors ${isActive
                                ? 'bg-blue-600 hover:bg-blue-700 text-white'
                                : 'hover:bg-gray-100 text-gray-600'
                            }`}
                        onClick={() => onFilterToggle(filter.value)}
                    >
                        {filter.label}
                        {isActive && <X className="ml-1 h-3 w-3" />}
                    </Badge>
                );
            })}

            {activeFilters.length > 0 && (
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={onClearAll}
                    className="text-xs text-gray-400 hover:text-gray-600 h-7 px-2"
                >
                    Clear all
                </Button>
            )}
        </div>
    );
}
