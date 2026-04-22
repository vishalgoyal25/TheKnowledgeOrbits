/**
 * App favicon — generated programmatically via Next.js ImageResponse.
 * Eliminates the browser's 404 request for /favicon.ico.
 *
 * Served at /icon.png (32 × 32) and automatically linked in <head>.
 * No external file or dependency needed — bundled into the build.
 */

import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          fontSize: 14,
          background: "linear-gradient(135deg, #1d4ed8 0%, #7c3aed 100%)",
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "white",
          fontWeight: 700,
          fontFamily: "sans-serif",
          borderRadius: "6px",
          letterSpacing: "-0.5px",
        }}
      >
        TK
      </div>
    ),
    { ...size },
  );
}
