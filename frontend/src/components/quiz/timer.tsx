/**
 * Timer Component
 * 
 * Countdown timer with visual urgency visualization.
 */

'use client';

import { useEffect, useState } from 'react';
import { Clock } from 'lucide-react';

interface TimerProps {
    initialSeconds: number;
    onExpire: () => void;
}

export default function Timer({ initialSeconds, onExpire }: TimerProps) {
    const [secondsRemaining, setSecondsRemaining] = useState(initialSeconds);

    useEffect(() => {
        // If timer expired
        if (secondsRemaining <= 0) {
            onExpire();
            return;
        }

        // Tick every second
        const interval = setInterval(() => {
            setSecondsRemaining((prev) => {
                if (prev <= 1) {
                    clearInterval(interval);
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);

        return () => clearInterval(interval);
    }, [secondsRemaining, onExpire]);

    // Format time mm:ss
    const formatTime = (totalSeconds: number) => {
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = totalSeconds % 60;
        return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    };

    // Visual urgency classes
    const getTimerColor = (seconds: number) => {
        if (seconds <= 60) return 'text-red-600 font-bold animate-pulse'; // Last minute
        if (seconds <= 300) return 'text-orange-600 font-semibold'; // Last 5 mins
        return 'text-blue-600 font-medium';
    };

    return (
        <div className={`flex items-center gap-2 text-lg ${getTimerColor(secondsRemaining)}`}>
            <Clock className="h-5 w-5" />
            <span className="tabular-nums tracking-wider">
                {formatTime(secondsRemaining)}
            </span>
        </div>
    );
}
