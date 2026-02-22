"use client";

import { FileQuestion } from "lucide-react";

interface EmptyStateProps {
  title?: string;
  description?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
}

export default function EmptyState({
  title = "Nothing here yet",
  description = "Get started by creating something new.",
  icon,
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center gap-4">
      <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center text-gray-400">
        {icon || <FileQuestion className="h-8 w-8" />}
      </div>
      <div>
        <h3 className="font-semibold text-gray-900 text-lg">{title}</h3>
        <p className="text-sm text-gray-500 mt-1 max-w-xs">{description}</p>
      </div>
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
