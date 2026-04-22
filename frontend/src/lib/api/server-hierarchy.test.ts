/**
 * src/lib/api/server-hierarchy.test.ts
 * ─────────────────────────────────────
 * Unit tests for getHierarchyData() — ISR server-side hierarchy fetcher.
 *
 * All tests mock global fetch to avoid real network calls.
 * AbortSignal.timeout is polyfilled if the jsdom environment lacks it.
 */

import { getHierarchyData } from "@/lib/api/server-hierarchy";

// ── Environment setup ──────────────────────────────────────────────────────────

// AbortSignal.timeout is a newer browser/Node API; jsdom may not have it.
// Polyfill with a no-op signal so the module under test loads without errors.
if (!("timeout" in AbortSignal)) {
  Object.defineProperty(AbortSignal, "timeout", {
    value: (_ms: number) => new AbortController().signal,
    configurable: true,
    writable: true,
  });
}

const mockFetch = jest.fn();
global.fetch = mockFetch as typeof global.fetch;

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeOkResponse(body: unknown) {
  return { ok: true, json: async () => body } as Response;
}

function makeErrorResponse() {
  return { ok: false, json: jest.fn() } as unknown as Response;
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("getHierarchyData", () => {
  beforeEach(() => mockFetch.mockReset());

  // ── Error / empty paths ────────────────────────────────────────────────────

  it("returns [] when fetch throws (network error / Render cold-start timeout)", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));
    const result = await getHierarchyData();
    expect(result).toEqual([]);
  });

  it("returns [] when response is not ok (e.g. 500 from backend)", async () => {
    mockFetch.mockResolvedValue(makeErrorResponse());
    const result = await getHierarchyData();
    expect(result).toEqual([]);
  });

  it("returns [] when response body is not an array", async () => {
    mockFetch.mockResolvedValue(makeOkResponse({ unexpected: "shape" }));
    const result = await getHierarchyData();
    expect(result).toEqual([]);
  });

  it("returns [] when response is an empty array", async () => {
    mockFetch.mockResolvedValue(makeOkResponse([]));
    const result = await getHierarchyData();
    expect(result).toEqual([]);
  });

  // ── Happy paths ────────────────────────────────────────────────────────────

  it("returns subjects directly when response is a flat HierarchySubject array", async () => {
    const subjects = [
      { id: "polity", name: "Indian Polity & Constitution", modules: [] },
      { id: "history", name: "Modern Indian History", modules: [] },
    ];
    mockFetch.mockResolvedValue(makeOkResponse(subjects));
    const result = await getHierarchyData();
    expect(result).toEqual(subjects);
  });

  it("flattens programs.subjects when response is a programs-wrapper structure", async () => {
    const programs = [
      {
        id: "upsc",
        name: "UPSC CSE",
        subjects: [
          { id: "polity", name: "Indian Polity", modules: [] },
          { id: "economy", name: "Indian Economy", modules: [] },
        ],
      },
    ];
    mockFetch.mockResolvedValue(makeOkResponse(programs));
    const result = await getHierarchyData();
    expect(result).toHaveLength(2);
    expect(result[0].id).toBe("polity");
    expect(result[1].id).toBe("economy");
  });

  it("flattens subjects from multiple programs into a single list", async () => {
    const programs = [
      { id: "prog1", subjects: [{ id: "s1", name: "S1", modules: [] }] },
      {
        id: "prog2",
        subjects: [
          { id: "s2", name: "S2", modules: [] },
          { id: "s3", name: "S3", modules: [] },
        ],
      },
    ];
    mockFetch.mockResolvedValue(makeOkResponse(programs));
    const result = await getHierarchyData();
    expect(result).toHaveLength(3);
  });

  // ── Implementation details ─────────────────────────────────────────────────

  it("calls fetch exactly once per invocation", async () => {
    mockFetch.mockResolvedValue(makeOkResponse([]));
    await getHierarchyData();
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it("calls fetch with /knowledge/hierarchy/ endpoint", async () => {
    mockFetch.mockResolvedValue(makeOkResponse([]));
    await getHierarchyData();
    const calledUrl: string = mockFetch.mock.calls[0][0] as string;
    expect(calledUrl).toMatch(/\/knowledge\/hierarchy\//);
  });
});
