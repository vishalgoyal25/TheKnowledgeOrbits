/* eslint-disable no-console */
/* eslint-env node */
/* eslint-disable @typescript-eslint/no-var-requires */
/**
 * wait-for-backend.js
 *
 * This script is executed during the Vercel build process BEFORE 'next build'.
 * It ensures that the Render backend and Supabase database are fully awake
 * and responding before Next.js attempts to generate static pages (ISR).
 *
 * This effectively breaks the "Death Loop" by failing the build if the
 * backend isn't ready, instead of caching empty/error pages.
 */

const https = require("https");

// 1. Smart URL Handling (Matches src/lib/api/client.ts)
const RAW_API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "https://theknowledgeorbits-backend.onrender.com";
const API_BASE = RAW_API_URL.replace(/\/+$/, "");

// Construct the health endpoint intelligently
const HEALTH_ENDPOINT = API_BASE.includes("/api/")
  ? `${API_BASE}/health/deep/`
  : `${API_BASE}/api/v1/health/deep/`;

// 2. Proactive "Warm-up" Pulse (Phase 5 Logic)
console.log("🔥 [Phase 5] Proactively warming up Render backend...");
https
  .get(HEALTH_ENDPOINT.replace("/health/deep/", "/health/"), () => {
    // We don't wait for this one, it's just a "kickstart" to trigger the cold boot
    console.log("📡 [Warm-up] Pulse sent to lightweight health endpoint.");
  })
  .on("error", () => {});

const MAX_RETRIES = 120; // 10 minutes total (120 * 5s)
const RETRY_INTERVAL = 5000; // 5 seconds

// CI Bypass: Skip waiting if we are just checking build integrity in GitHub Actions
if (process.env.SKIP_BACKEND_WAIT === "true") {
  console.log(
    "⏩ [CI Bypass] Skipping backend wait for build integrity check.",
  );
  process.exit(0);
}

console.log(`🚀 [Pre-Build] Waiting for backend at: ${HEALTH_ENDPOINT}`);

function checkHealth(attempt = 1) {
  return new Promise((resolve) => {
    console.log(
      `📡 [Attempt ${attempt}/${MAX_RETRIES}] Pinging Deep Health...`,
    );

    const req = https.get(HEALTH_ENDPOINT, (res) => {
      res.on("data", () => {
        /* we just need the status code */
      });

      res.on("end", () => {
        if (res.statusCode === 200) {
          console.log("✅ [Success] Backend is Hot and Database is Connected!");
          resolve(true);
        } else if (res.statusCode === 404 && attempt < 30) {
          // Render Load Balancer often returns 404 while the dynamic routing table is updating
          console.log(
            "⏳ [Waking Up] Render Routing Table update... (Status 404)",
          );
          resolve(false);
        } else if (res.statusCode === 503) {
          console.warn(
            "🗄️ [DB Wakeup] Backend is up, but Database is still resuming... (Status 503)",
          );
          resolve(false);
        } else {
          console.warn(
            `⚠️ [Warning] Backend returned status ${res.statusCode}.`,
          );
          resolve(false);
        }
      });
    });

    req.on("error", (err) => {
      console.warn(`❌ [Error] Connection failed: ${err.message}`);
      resolve(false);
    });

    // Timeout if the request takes too long
    req.setTimeout(10000, () => {
      req.destroy();
      console.warn("🕒 [Timeout] Request to backend timed out.");
      resolve(false);
    });
  });
}

async function start() {
  for (let i = 1; i <= MAX_RETRIES; i++) {
    const isHealthy = await checkHealth(i);

    if (isHealthy) {
      process.exit(0); // Success! Continue to next build
    }

    if (i < MAX_RETRIES) {
      console.log(
        `😴 Sleeping for ${RETRY_INTERVAL / 1000}s before next retry...`,
      );
      await new Promise((resolve) => setTimeout(resolve, RETRY_INTERVAL));
    }
  }

  console.error(
    "🛑 [FATAL] Backend failed to wake up after 10 minutes. Aborting build to prevent scorched cache.",
  );
  console.error(
    "💡 TIP: If this persists, manually visit the backend URL or check Supabase project status.",
  );
  process.exit(1); // Fail the build
}

start();
