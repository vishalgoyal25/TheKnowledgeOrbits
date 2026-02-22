"use client";

import { AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ErrorMessageProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export default function ErrorMessage({
  title = "Something went wrong",
  message = "An unexpected error occurred. Please try again.",
  onRetry,
  className = "",
}: ErrorMessageProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center py-12 px-6 text-center gap-4 ${className}`}
    >
      <div className="w-14 h-14 bg-red-50 rounded-full flex items-center justify-center">
        <AlertCircle className="h-7 w-7 text-red-500" />
      </div>
      <div>
        <h3 className="font-semibold text-gray-900 text-lg">{title}</h3>
        <p className="text-sm text-gray-500 mt-1 max-w-sm">{message}</p>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry} className="gap-2">
          <RefreshCw className="h-4 w-4" />
          Try Again
        </Button>
      )}
    </div>
  );
}
