/**
 * TanStack Query provider
 */

"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 1 minute
            gcTime: 30 * 60 * 1000, // 30 minutes
            refetchOnWindowFocus: false,
            // Silent Resilience Strategy:
            // 1. Retry up to 10 times for 503 (Service Unavailable)
            retry: (failureCount, error) => {
              // Safely check for Axios error status without using 'any'
              const status = (error as { response?: { status: number } })
                ?.response?.status;

              // Always retry on 503 (Render Cold Start)
              if (status === 503 && failureCount < 10) {
                return true;
              }
              // Standard retry for other errors
              return failureCount < 2;
            },
            // 2. Exponential backoff for 503 retries
            retryDelay: (attemptIndex) =>
              Math.min(1000 * 2 ** attemptIndex, 10000),
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
