/**
 * src/app/page.test.tsx
 * ─────────────────────
 * Unit tests for the ISR home page server component wrapper (src/app/page.tsx).
 *
 * Strategy:
 *   - Mock global fetch so no real HTTP calls are made.
 *   - Mock HomePageClient to capture the initialTodayArticles prop it receives.
 *   - Call Page() directly (it's an async function) and render the result.
 *
 * What we verify:
 *   1. Articles are sorted by order_on_date before being passed down.
 *   2. Empty array is passed when fetch throws (Render offline / timeout).
 *   3. Empty array is passed when the API returns a non-ok response.
 */

import { render, screen } from "@testing-library/react";
import type { DailyCaArticleList } from "@/lib/api/daily-ca";

// ── AbortSignal.timeout polyfill ───────────────────────────────────────────────
if (!("timeout" in AbortSignal)) {
  Object.defineProperty(AbortSignal, "timeout", {
    value: (_ms: number) => new AbortController().signal,
    configurable: true,
    writable: true,
  });
}

// ── Mock HomePageClient so we don't render the full heavyweight component ──────
// Props are serialised into a data attribute so test assertions can read them.
jest.mock("@/components/home/home-page-client", () => ({
  __esModule: true,
  default: function MockHomePageClient({
    initialTodayArticles,
  }: {
    initialTodayArticles: DailyCaArticleList[];
  }) {
    return (
      <div
        data-testid="home-page-client"
        data-articles={JSON.stringify(initialTodayArticles)}
      />
    );
  },
}));

// ── Mock fetch ─────────────────────────────────────────────────────────────────
const mockFetch = jest.fn();
global.fetch = mockFetch as typeof global.fetch;

// ── Helper to build a minimal DailyCaArticleList fixture ──────────────────────
function makeArticle(
  order: number,
  overrides: Partial<DailyCaArticleList> = {},
): DailyCaArticleList {
  return {
    id: `id-${order}`,
    slug: `slug-${order}`,
    title: `Article ${order}`,
    subject_name: "Indian Polity",
    gs_paper: "GS2",
    news_category: "national",
    published_date: "2026-04-22",
    news_context: "",
    hero_image_url: null,
    quality_score: 8.0,
    order_on_date: order,
    topic_name: null,
    tags: [],
    ...overrides,
  };
}

function makeOkResponse(articles: DailyCaArticleList[]) {
  return {
    ok: true,
    json: async () => ({
      date: "2026-04-22",
      count: articles.length,
      articles,
    }),
  } as Response;
}

// ── Tests ──────────────────────────────────────────────────────────────────────

describe("Page (ISR home page server component)", () => {
  beforeEach(() => mockFetch.mockReset());

  async function getPassedArticles(): Promise<DailyCaArticleList[]> {
    // Dynamically import so the module picks up the mock state each time.
    const { default: Page } = await import("@/app/page");
    const element = await Page();
    render(element);
    const el = screen.getByTestId("home-page-client");
    return JSON.parse(el.getAttribute("data-articles") ?? "[]");
  }

  it("passes an empty array when fetch throws (network error / Render offline)", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));
    const articles = await getPassedArticles();
    expect(articles).toEqual([]);
  });

  it("passes an empty array when API responds with a non-ok status", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      json: jest.fn(),
    } as unknown as Response);
    const articles = await getPassedArticles();
    expect(articles).toEqual([]);
  });

  it("passes articles sorted ascending by order_on_date", async () => {
    // Provide articles intentionally out of order
    const unsorted = [makeArticle(3), makeArticle(1), makeArticle(2)];
    mockFetch.mockResolvedValue(makeOkResponse(unsorted));
    const articles = await getPassedArticles();
    expect(articles.map((a) => a.order_on_date)).toEqual([1, 2, 3]);
  });

  it("passes all articles received from the API (no silent drops)", async () => {
    const five = [1, 2, 3, 4, 5].map((n) => makeArticle(n));
    mockFetch.mockResolvedValue(makeOkResponse(five));
    const articles = await getPassedArticles();
    expect(articles).toHaveLength(5);
  });

  it("passes an empty array when API returns zero articles for the day", async () => {
    mockFetch.mockResolvedValue(makeOkResponse([]));
    const articles = await getPassedArticles();
    expect(articles).toEqual([]);
  });

  it("calls fetch with the /daily-ca/today/ endpoint", async () => {
    mockFetch.mockResolvedValue(makeOkResponse([]));
    await getPassedArticles();
    const calledUrl: string = mockFetch.mock.calls[0][0] as string;
    expect(calledUrl).toMatch(/\/daily-ca\/today\//);
  });
});
