/* eslint-disable no-console */
import { NextRequest, NextResponse } from "next/server";
import { revalidatePath } from "next/cache";

/**
 * Next.js On-Demand Revalidation Route
 *
 * This endpoint allows external services (like GitHub Actions) to trigger
 * a refresh of static pages even before the ISR timer expires.
 *
 * Usage: GET /api/revalidate?secret=YOUR_SECRET
 */
export async function GET(request: NextRequest) {
  const secret = request.nextUrl.searchParams.get("secret");
  const path = request.nextUrl.searchParams.get("path") || "all";

  // Validate Secret
  if (secret !== process.env.REVALIDATE_SECRET) {
    console.warn("🚫 [Revalidate] Unauthorized attempt with invalid secret");
    return NextResponse.json({ message: "Invalid secret" }, { status: 401 });
  }

  try {
    console.log(`🔄 [Revalidate] Triggering revalidation for path: ${path}`);

    if (path === "all") {
      // Refresh only the index pages themselves — NOT "layout" scope, which
      // invalidates every dynamic page under each route (every article, every
      // topic) in one call. That amplification is what was burning through
      // Vercel's free-tier ISR-write quota. Individual new content still gets
      // revalidated on its own specific path by the caller.
      revalidatePath("/articles");
      revalidatePath("/topics");
      revalidatePath("/current-affairs");
      console.log(
        "✅ [Revalidate] Successfully queued Articles, Topics, and CA index pages for refresh",
      );
    } else {
      revalidatePath(path);
      console.log(`✅ [Revalidate] Successfully queued ${path} for refresh`);
    }

    return NextResponse.json({
      revalidated: true,
      now: Date.now(),
      target: path,
    });
  } catch (err) {
    console.error("❌ [Revalidate] Error during path revalidation:", err);
    return NextResponse.json(
      { message: "Error revalidating" },
      { status: 500 },
    );
  }
}
