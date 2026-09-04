"use client";

/**
 * Fire-and-forget read beacon. Mount it on a content page; it POSTs once per
 * mount to /api/v1/telemetry/read/ and renders nothing.
 *
 * Deliberately uses raw fetch instead of lib/api/client.ts. That client attaches
 * the auth token and runs a response interceptor which, on a 401, refreshes the
 * token and can clear tokens or redirect to /auth/login. Telemetry must never be
 * able to touch auth state or navigate the reader, so this path stays isolated:
 * no interceptors, no retries, no credentials, no error surfaced.
 *
 * Duplicate reads are not a client concern — the DB rejects them via the
 * (content_type, content_id, ip_hash, read_date) unique constraint.
 */
import { useEffect } from "react";

export type ReadContentType = "daily_ca_article" | "concept" | "article";

interface ReadBeaconProps {
  contentType: ReadContentType;
  contentId: string;
}

export default function ReadBeacon({
  contentType,
  contentId,
}: ReadBeaconProps) {
  useEffect(() => {
    // Guards against the known bad-slug path (/daily-ca/article/null/) reaching
    // the endpoint and being rejected by serializer validation as junk.
    if (!contentId || contentId === "null" || contentId === "undefined") {
      return;
    }

    const base =
      process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

    void fetch(`${base}/telemetry/read/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content_type: contentType,
        content_id: contentId,
      }),
      keepalive: true,
    }).catch(() => {
      // Intentionally silent. A failed beacon is invisible to the reader.
    });
  }, [contentType, contentId]);

  return null;
}
