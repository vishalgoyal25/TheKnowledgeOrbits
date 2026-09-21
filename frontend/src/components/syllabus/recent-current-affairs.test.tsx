/**
 * src/components/syllabus/recent-current-affairs.test.tsx
 * ────────────────────────────────────────────────────────
 * G3.14c — the client-side "In the news" block on the hierarchy pages.
 *
 * The API module is mocked so no HTTP happens; `next/image` is replaced by a
 * plain <img> (the real one needs Next's loader context).
 *
 * What we verify:
 *   1. An empty first page renders NOTHING — no frame, no heading.
 *   2. A page renders its rows (thumb, GS badge, date, title → article URL)
 *      and shows "Load more" only when `has_more` is true.
 *   3. "Load more" appends the next page with `offset = items so far`, and the
 *      button disappears on the last page.
 *   4. An API failure renders nothing (never a red box on a public page).
 *   5. Rows without a slug are dropped before they can be linked.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ImgHTMLAttributes } from "react";

import type { ByNodeResponse, DailyCaArticleList } from "@/lib/api/daily-ca";
import RecentCurrentAffairs from "./recent-current-affairs";

jest.mock("next/image", () => ({
  __esModule: true,
  // A plain <img> stands in for next/image (needs Next's loader context).
  default: (props: Record<string, unknown>) => {
    const { fill: _fill, ...rest } = props;
    void _fill;
    return <img {...(rest as ImgHTMLAttributes<HTMLImageElement>)} />;
  },
}));

// `mock` prefix: jest hoists the factory above this declaration and only
// lets it reference variables named that way.
const mockGetArticlesByNode = jest.fn();
jest.mock("@/lib/api/daily-ca", () => ({
  __esModule: true,
  getArticlesByNode: (...args: unknown[]) => mockGetArticlesByNode(...args),
}));
const getArticlesByNode = mockGetArticlesByNode;

function article(n: number, extra: Partial<DailyCaArticleList> = {}) {
  return {
    id: `id-${n}`,
    slug: `2099-05-${String(n).padStart(2, "0")}-article-${n}`,
    title: `Article number ${n}`,
    subject_name: "Polity",
    gs_paper: "GS2",
    news_category: "national",
    published_date: `2099-05-${String(n).padStart(2, "0")}`,
    news_context: "",
    hero_image_url:
      n % 2 ? "https://res.cloudinary.com/x/image/upload/a.jpg" : null,
    quality_score: 9,
    order_on_date: 1,
    topic_name: "Fundamental Rights",
    tags: [],
    ...extra,
  } as DailyCaArticleList;
}

function page(rows: DailyCaArticleList[], hasMore: boolean, count: number) {
  const body: ByNodeResponse = {
    scope: "topic",
    node_id: "node-1",
    count,
    limit: 10,
    offset: 0,
    has_more: hasMore,
    articles: rows,
  };
  return body;
}

beforeEach(() => {
  getArticlesByNode.mockReset();
});

describe("RecentCurrentAffairs", () => {
  it("renders nothing when the node has no articles", async () => {
    getArticlesByNode.mockResolvedValueOnce(page([], false, 0));
    const { container } = render(
      <RecentCurrentAffairs scope="topic" nodeId="node-1" />,
    );
    await waitFor(() => expect(getArticlesByNode).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(container).toBeEmptyDOMElement());
    expect(screen.queryByText("In the news")).toBeNull();
  });

  it("renders nothing when the API fails", async () => {
    getArticlesByNode.mockRejectedValueOnce(new Error("502"));
    const { container } = render(
      <RecentCurrentAffairs scope="module" nodeId="node-1" />,
    );
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("renders the rows and a Load more button when there is more", async () => {
    const rows = Array.from({ length: 10 }, (_, i) => article(i + 1));
    getArticlesByNode.mockResolvedValueOnce(page(rows, true, 12));

    render(<RecentCurrentAffairs scope="topic" nodeId="node-1" />);

    expect(await screen.findByText("Article number 1")).toBeTruthy();
    expect(screen.getAllByRole("link")).toHaveLength(10);
    expect(
      screen.getByText("Article number 1").closest("a")?.getAttribute("href"),
    ).toBe("/daily-ca/article/2099-05-01-article-1");
    expect(screen.getByText("12")).toBeTruthy(); // the count in the header
    expect(screen.getAllByText("GS2")).toHaveLength(10);
    // Odd rows carry a hero image; alt="" makes them presentational, so count
    // the elements rather than the (absent) img role.
    expect(document.querySelectorAll("img")).toHaveLength(5);
    expect(screen.getByRole("button", { name: "Load more" })).toBeTruthy();
    expect(getArticlesByNode).toHaveBeenCalledWith("topic", "node-1", {
      limit: 10,
      offset: 0,
    });
  });

  it("Load more appends the next page and hides itself on the last one", async () => {
    const first = Array.from({ length: 10 }, (_, i) => article(i + 1));
    const second = [article(11), article(12)];
    getArticlesByNode
      .mockResolvedValueOnce(page(first, true, 12))
      .mockResolvedValueOnce({ ...page(second, false, 12), offset: 10 });

    render(<RecentCurrentAffairs scope="subject" nodeId="node-9" />);
    await screen.findByText("Article number 10");

    fireEvent.click(screen.getByRole("button", { name: "Load more" }));

    expect(await screen.findByText("Article number 12")).toBeTruthy();
    expect(screen.getAllByRole("link")).toHaveLength(12);
    expect(screen.queryByRole("button", { name: "Load more" })).toBeNull();
    expect(getArticlesByNode).toHaveBeenLastCalledWith("subject", "node-9", {
      limit: 10,
      offset: 10,
    });
  });

  it("drops rows without a slug", async () => {
    getArticlesByNode.mockResolvedValueOnce(
      page([article(1), article(2, { slug: "" })], false, 2),
    );
    render(<RecentCurrentAffairs scope="topic" nodeId="node-1" />);
    await screen.findByText("Article number 1");
    expect(screen.getAllByRole("link")).toHaveLength(1);
    expect(screen.queryByText("Article number 2")).toBeNull();
  });
});
