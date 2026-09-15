/**
 * Pure helpers over the subject tree (`/book/tree/<subject>/`) shared by the
 * knowledge map and the ISR hierarchy pages (G3.13). No React, no fetch.
 *
 * The tree is the ONE structure that knows nesting, slugs and `has_content`
 * for every node in a subject, and it is Redis-cached server-side — so a page
 * fetches it once and derives everything else here.
 */

import type { SubjectTree, TreeModule, TreeTopic } from "@/types/book-content";

/** Every topic under `topics`, depth-first, including nested subtopics. */
export function flattenTopics(
  topics: TreeTopic[],
  acc: TreeTopic[] = [],
): TreeTopic[] {
  for (const t of topics) {
    acc.push(t);
    flattenTopics(t.subtopics, acc);
  }
  return acc;
}

export function countWithContent(topics: TreeTopic[]): number {
  return flattenTopics(topics).filter((t) => t.has_content).length;
}

/** The module with this id, or null. */
export function findModule(
  tree: SubjectTree,
  moduleId: string,
): TreeModule | null {
  return tree.modules.find((m) => m.id === moduleId) ?? null;
}

/** Depth-first search for a topic by id anywhere under `topics`. */
export function findTopic(
  topics: TreeTopic[],
  topicId: string,
): TreeTopic | null {
  for (const t of topics) {
    if (t.id === topicId) return t;
    const below = findTopic(t.subtopics, topicId);
    if (below) return below;
  }
  return null;
}

export interface Crumb {
  id: string;
  slug: string | null;
  name: string;
}

/**
 * Subject › Module › Topic › … › target. Each crumb carries its slug so a page
 * can link it (subject → /subjects/<slug>, module → /modules/<slug>, topics →
 * /topics/<slug>). Empty if the id is not in this tree.
 */
export function trailTo(tree: SubjectTree, targetId: string): Crumb[] {
  const subject: Crumb = { id: tree.id, slug: tree.slug, name: tree.name };
  if (targetId === tree.id) return [subject];
  for (const mod of tree.modules) {
    const modCrumb: Crumb = { id: mod.id, slug: mod.slug, name: mod.name };
    if (mod.id === targetId) return [subject, modCrumb];
    const path = pathTo(mod.topics, targetId);
    if (path) return [subject, modCrumb, ...path];
  }
  return [];
}

function pathTo(topics: TreeTopic[], targetId: string): Crumb[] | null {
  for (const t of topics) {
    const here: Crumb = { id: t.id, slug: t.slug, name: t.name };
    if (t.id === targetId) return [here];
    const below = pathTo(t.subtopics, targetId);
    if (below) return [here, ...below];
  }
  return null;
}
