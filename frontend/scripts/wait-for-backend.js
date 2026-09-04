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

const http = require("http");
const https = require("https");
const path = require("path");

// A bare `node` process does NOT read .env.local — only `next` does. Without
// this, NEXT_PUBLIC_API_URL is undefined here, the Render fallback below wins,
// and the gate cheerfully verifies a backend the build will never call: a green
// "Backend is Hot" immediately followed by ECONNREFUSED against localhost.
// Cost two failed local builds on 2026-09-03/04 before it was spotted.
//
// Anchored to __dirname, not cwd, so it resolves the same however it is invoked.
// Wrapped because a resolution failure must degrade to the previous behaviour
// rather than break the Vercel build — where the variable is a real process env
// var and this call changes nothing.
try {
  require("@next/env").loadEnvConfig(path.join(__dirname, ".."));
} catch {
  console.warn("⚠️ [Env] @next/env unavailable; using process env only.");
}

// 1. Smart URL Handling (Matches src/lib/api/client.ts)
const RAW_API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "https://theknowledgeorbits-backend.onrender.com";
const API_BASE = RAW_API_URL.replace(/\/+$/, "");

// Construct the health endpoint intelligently
const HEALTH_ENDPOINT = API_BASE.includes("/api/")
  ? `${API_BASE}/health/deep/`
  : `${API_BASE}/api/v1/health/deep/`;

// Local development points at http://localhost:8000. `https.get` on an http:
// URL throws 'Protocol "http:" not supported' synchronously, before a request
// object exists — so the req.on("error") handler below could never catch it.
const client = HEALTH_ENDPOINT.startsWith("https:") ? https : http;

// 2. Proactive "Warm-up" Pulse (Phase 5 Logic)
console.log(`🔥 [Phase 5] Proactively warming up backend at ${API_BASE}...`);
client
  .get(HEALTH_ENDPOINT.replace("/health/deep/", "/health/"), (res) => {
    // We don't wait for this one, it's just a "kickstart" to trigger the cold boot.
    // resume() drains and discards the body so the socket closes cleanly —
    // without it Node leaves the response unread and the server logs a broken
    // pipe writing into a socket nobody is listening to.
    res.resume();
    console.log("📡 [Warm-up] Pulse sent to lightweight health endpoint.");
  })
  .on("error", () => {});

// The long retry budget exists for Render cold starts, which can take minutes.
// A local server has no cold start: it is either listening or it is not, so
// retrying localhost 120 times would stall a developer for 10 minutes to learn
// something knowable in 15 seconds.
const IS_LOCAL = /^https?:\/\/(localhost|127\.0\.0\.1)/.test(API_BASE);
const MAX_RETRIES = IS_LOCAL ? 3 : 120; // 15s locally, 10 min against Render
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

    const req = client.get(HEALTH_ENDPOINT, (res) => {
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

  const waitedSeconds = Math.round((MAX_RETRIES * RETRY_INTERVAL) / 1000);
  console.error(
    `🛑 [FATAL] No response from ${HEALTH_ENDPOINT} within ${waitedSeconds}s. Aborting build to prevent scorched cache.`,
  );
  console.error(
    IS_LOCAL
      ? "💡 TIP: Is the local backend running? `python backend/manage.py runserver`"
      : "💡 TIP: If this persists, manually visit the backend URL or check Supabase project status.",
  );
  process.exit(1); // Fail the build
}

start();
