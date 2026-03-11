/**
 * Reading Progress Tracker - Client Component
 * Handles scroll progress tracking and fixed top progress bar.
 */

"use client";

import { useEffect } from "react";
import { useReadingProgress } from "@/lib/hooks/use-reading-progress";
import ReadingProgress from "./reading-progress";

interface Props {
  articleId: string;
}

export default function ReadingProgressTracker({ articleId }: Props) {
  const { progress, updateProgress } = useReadingProgress(articleId);

  useEffect(() => {
    const handleScroll = () => {
      const scrollTop = window.scrollY;
      const scrollHeight =
        document.documentElement.scrollHeight - window.innerHeight;
      const percent = scrollHeight > 0 ? (scrollTop / scrollHeight) * 100 : 0;

      updateProgress(Math.min(Math.max(percent, 0), 100), scrollTop);
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, [articleId, updateProgress]);

  // Restore scroll position on mount
  useEffect(() => {
    if (progress?.last_position) {
      // Small timeout to allow content to fully render
      setTimeout(() => {
        window.scrollTo({
          top: progress.last_position,
          behavior: "smooth",
        });
      }, 500);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <ReadingProgress percent={progress?.percent_read || 0} />;
}
