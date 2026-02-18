'use client';

interface Props {
    percent: number;
}

export default function ReadingProgress({ percent }: Props) {
    return (
        <div className="fixed top-0 left-0 w-full h-1 bg-gray-200 z-50">
            <div
                className="h-full bg-blue-600 transition-all duration-300"
                style={{ width: `${percent}%` }}
            />
        </div>
    );
}
