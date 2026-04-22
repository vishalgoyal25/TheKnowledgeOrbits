/**
 * src/components/layout/header.staleness-guard.test.ts
 * ──────────────────────────────────────────────────────
 * Pure unit tests for the P3.5 staleness-guard initialization logic in header.tsx.
 *
 * The guard controls whether the client re-fetches hierarchy from the backend
 * after a page load. The critical fix (P3.5 bug):
 *
 *   BEFORE (buggy):
 *     initialHierarchy ? Date.now() : 0
 *     → [] (empty array) is truthy in JS, so a cold-start ISR miss that
 *       returns [] would set the ref to Date.now(), permanently blocking
 *       the client re-fetch fallback.
 *
 *   AFTER (fixed):
 *     initialHierarchy && initialHierarchy.length > 0 ? Date.now() : 0
 *     → [] correctly returns 0 → re-fetch fires → navbar fills in.
 *
 * These tests validate the fixed expression in isolation (no component render
 * needed — the logic is a pure conditional).
 */

import type { HierarchySubject } from "@/lib/types";

// ── The exact expression used in header.tsx ───────────────────────────────────
function stalenessGuardInitialValue(
  initialHierarchy: HierarchySubject[] | undefined,
): number {
  return initialHierarchy && initialHierarchy.length > 0 ? Date.now() : 0;
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("P3.5 staleness guard initialization logic", () => {
  // ── Cases that must return 0 (force client re-fetch) ──────────────────────

  it("returns 0 for undefined (prop not passed from layout)", () => {
    expect(stalenessGuardInitialValue(undefined)).toBe(0);
  });

  it("returns 0 for [] (ISR cold-start miss returned empty array)", () => {
    // This is the core regression: [] is truthy, so the old `initialHierarchy ?`
    // expression would return Date.now() here, blocking re-fetch forever.
    expect(stalenessGuardInitialValue([])).toBe(0);
  });

  // ── Cases that must return a timestamp (skip client re-fetch) ─────────────

  it("returns a positive timestamp when hierarchy has at least one subject", () => {
    const hierarchy: HierarchySubject[] = [
      {
        id: "polity",
        name: "Indian Polity & Constitution",
        description: "",
        modules: [],
      },
    ];
    const before = Date.now();
    const result = stalenessGuardInitialValue(hierarchy);
    const after = Date.now();
    expect(result).toBeGreaterThanOrEqual(before);
    expect(result).toBeLessThanOrEqual(after);
  });

  it("returns a positive timestamp when hierarchy has multiple subjects", () => {
    const hierarchy: HierarchySubject[] = [
      { id: "polity", name: "Indian Polity", description: "", modules: [] },
      { id: "economy", name: "Indian Economy", description: "", modules: [] },
    ];
    expect(stalenessGuardInitialValue(hierarchy)).toBeGreaterThan(0);
  });

  // ── Invariant ──────────────────────────────────────────────────────────────

  it("never returns a negative number for any input", () => {
    expect(stalenessGuardInitialValue(undefined)).toBeGreaterThanOrEqual(0);
    expect(stalenessGuardInitialValue([])).toBeGreaterThanOrEqual(0);
    expect(
      stalenessGuardInitialValue([
        { id: "x", name: "X", description: "", modules: [] },
      ]),
    ).toBeGreaterThanOrEqual(0);
  });
});
