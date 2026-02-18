'use client';

import { Loader2 } from 'lucide-react';

interface LoadingProps {
    message?: string;
    size?: 'sm' | 'md' | 'lg';
    fullScreen?: boolean;
    className?: string;
}

const sizeMap = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8',
    lg: 'h-12 w-12',
};

export default function Loading({
    message = 'Loading...',
    size = 'md',
    fullScreen = false,
    className = '',
}: LoadingProps) {
    const wrapper = fullScreen
        ? 'fixed inset-0 flex items-center justify-center bg-white/80 backdrop-blur-sm z-50'
        : 'flex flex-col items-center justify-center py-12 gap-3';

    return (
        <div className={`${wrapper} ${className}`}>
            <Loader2 className={`${sizeMap[size]} text-blue-600 animate-spin`} />
            {message && <p className="text-sm text-gray-500 animate-pulse">{message}</p>}
        </div>
    );
}
