/**
 * daily-ca-preprocess.ts
 * ──────────────────────
 * Shared markdown pre-processors for Daily CA article bodies.
 * Called before splitCallouts() and ReactMarkdown on both:
 *   - DailyCaArticle component (feed page)
 *   - /daily-ca/article/[slug] page (individual article)
 *
 * Pipeline: stripMetadataFooter → normalizeDidYouKnow
 */

// ── 1. Strip LLM metadata footer ─────────────────────────────────────────────
//
// The LLM sometimes appends a raw metadata line to the article body, e.g.:
//   CATEGORY: national TAGS: women's-reservation, parliament SOURCE: Indian Express
//
// This data is already stored in structured fields (category, tags, sources).
// Strip any line that looks like this footer so it never appears on screen.

export function stripMetadataFooter(md: string): string {
  return md
    .split("\n")
    .filter((line) => {
      const t = line.trim();
      if (!t) return true;
      // Combined line: CATEGORY: ... TAGS: ...
      if (/CATEGORY\s*:/i.test(t) && /TAGS\s*:/i.test(t)) return false;
      // Standalone labels that shouldn't appear in prose
      if (/^CATEGORY\s*:/i.test(t)) return false;
      if (/^TAGS\s*:/i.test(t)) return false;
      if (/^SOURCE\s*:/i.test(t)) return false;
      return true;
    })
    .join("\n");
}

// ── 2. Normalise "Did You Know?" into :::callout blocks ──────────────────────
//
// The LLM uses three different formats for this section:
//
//   Format A (heading):
//     ## Did You Know?
//     Body text on next line(s)…
//
//   Format B (inline bold paragraph):
//     **Did You Know?** Body text on same line…
//
//   Format C (already wrapped — pass through):
//     :::callout
//     …
//     :::
//
// This function normalises A and B into the :::callout syntax that
// splitCallouts() knows how to render as a styled card.

export function normalizeDidYouKnow(md: string): string {
  const lines = md.split("\n");
  const result: string[] = [];
  let i = 0;
  let insideCallout = false; // track existing :::callout blocks — don't re-wrap

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    // Track callout fence open/close so we never double-wrap
    if (/^:::callout/.test(trimmed)) {
      insideCallout = true;
      result.push(line);
      i++;
      continue;
    }
    if (trimmed === ":::") {
      insideCallout = false;
      result.push(line);
      i++;
      continue;
    }

    // ── Format A: heading (# / ## / ###) ──────────────────────────────────
    if (!insideCallout && /^#{1,3}\s+Did You Know\??/i.test(trimmed)) {
      const bodyLines: string[] = [];
      i++;
      while (i < lines.length && !/^#{1,3}\s/.test(lines[i].trim())) {
        bodyLines.push(lines[i]);
        i++;
      }
      // Trim surrounding blank lines
      while (bodyLines.length > 0 && bodyLines[0].trim() === "")
        bodyLines.shift();
      while (
        bodyLines.length > 0 &&
        bodyLines[bodyLines.length - 1].trim() === ""
      )
        bodyLines.pop();

      result.push(":::callout");
      result.push("**Did You Know?**");
      if (bodyLines.length > 0) {
        result.push("");
        result.push(...bodyLines);
      }
      result.push(":::");
      continue;
    }

    // ── Format B: inline bold  **Did You Know?** body on same line ────────
    if (!insideCallout && /^\*\*Did You Know\??\*\*/i.test(trimmed)) {
      // Extract everything after the **Did You Know?** prefix
      const body = trimmed.replace(/^\*\*Did You Know\??\*\*\s*/i, "").trim();
      result.push(":::callout");
      result.push("**Did You Know?**");
      if (body) {
        result.push("");
        result.push(body);
      }
      result.push(":::");
      i++;
      continue;
    }

    result.push(line);
    i++;
  }

  return result.join("\n");
}

// ── 3. Strip orphan callout fence markers ─────────────────────────────────────
//
// After normalizeDidYouKnow runs, any :::callout / ::: that still remain in the
// text are malformed remnants (unclosed block, inline-title not matched, etc.).
// ReactMarkdown renders them as visible text — strip them before rendering.

export function stripOrphanCalloutMarkers(md: string): string {
  return md
    .split("\n")
    .filter((line) => {
      const t = line.trim();
      // Remove any line that IS (or starts with) a callout fence marker
      if (/^:::callout/.test(t)) return false;
      if (t === ":::") return false;
      return true;
    })
    .join("\n");
}

// ── Combined pipeline ─────────────────────────────────────────────────────────

export function preprocessArticleBody(md: string): string {
  return normalizeDidYouKnow(stripMetadataFooter(md));
}
