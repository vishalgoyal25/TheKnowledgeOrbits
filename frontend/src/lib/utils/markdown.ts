/**
 * Markdown utilities for TheKnowledgeOrbits frontend.
 * Provides helpers for rendering and processing markdown content.
 */

/**
 * Strips markdown syntax from a string, returning plain text.
 * Useful for generating meta descriptions or search snippets.
 */
export function stripMarkdown(markdown: string): string {
    return markdown
        .replace(/#{1,6}\s+/g, '')           // headings
        .replace(/\*\*(.+?)\*\*/g, '$1')     // bold
        .replace(/\*(.+?)\*/g, '$1')         // italic
        .replace(/`{1,3}[^`]*`{1,3}/g, '')  // code
        .replace(/\[(.+?)\]\(.+?\)/g, '$1') // links
        .replace(/!\[.*?\]\(.+?\)/g, '')     // images
        .replace(/^[-*+]\s+/gm, '')          // list items
        .replace(/^\d+\.\s+/gm, '')          // ordered list
        .replace(/^>\s+/gm, '')              // blockquotes
        .replace(/---+/g, '')                // horizontal rules
        .replace(/\n{2,}/g, '\n')            // multiple newlines
        .trim();
}

/**
 * Truncates markdown-stripped text to a given character limit.
 */
export function markdownExcerpt(markdown: string, maxLength = 160): string {
    const plain = stripMarkdown(markdown);
    if (plain.length <= maxLength) return plain;
    return plain.slice(0, maxLength).replace(/\s+\S*$/, '') + '…';
}

/**
 * Estimates reading time in minutes for a markdown string.
 * Assumes average reading speed of 200 words per minute.
 */
export function estimateReadingTime(markdown: string): number {
    const plain = stripMarkdown(markdown);
    const wordCount = plain.split(/\s+/).filter(Boolean).length;
    return Math.max(1, Math.ceil(wordCount / 200));
}

/**
 * Extracts the first heading from a markdown string.
 */
export function extractTitle(markdown: string): string | null {
    const match = markdown.match(/^#{1,6}\s+(.+)/m);
    return match ? match[1].trim() : null;
}
