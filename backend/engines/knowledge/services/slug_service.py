"""
Slug minting for the syllabus hierarchy — Subject, Module, Topic.

WHY (G3.10, 2026-09-14)
  The three hierarchy models are identified by UUID only, so every public URL
  that names one reads as /topics/303c5747-9681-4c45-92a2-0cc51c9f8c07. A
  readable, keyword-bearing path is both a ranking signal and a click-through
  signal, and daily-CA articles already have one. This is the one place slugs
  come from, so every creation path — seed command, ingestor, admin, shell —
  mints them the same way.

RULES
  - slugify(name), truncated to fit the column with room for a suffix.
  - Globally unique per model. Module and topic names repeat across parents
    ("Introduction", "Overview"), so a collision takes the next free numeric
    suffix: introduction, introduction-2, introduction-3. Deterministic, and
    the first-seen row keeps the clean form.
  - A slug is set once and never rewritten on rename: URLs are promises.
    Renaming a node is an editorial act; re-slugging is a separate, explicit one.
  - Works against any DB alias, because the backfill migration runs on both
    local and Supabase and must produce identical slugs on each.
"""

from django.db.models import Model
from django.utils.text import slugify

# Longest suffix we will ever append is "-9999" (5 chars); keep a little slack.
_SUFFIX_ROOM = 6
_FALLBACK = "node"


def unique_slug(
    model: type[Model],
    name: str,
    *,
    max_length: int,
    using: str = "default",
    exclude_pk: object | None = None,
) -> str:
    """
    Return a slug for `name` that no other row of `model` on `using` holds.

    `exclude_pk` lets a row re-check its own slug without colliding with itself
    (used by save() when the slug is already set and valid).
    """
    base = slugify(name)[: max_length - _SUFFIX_ROOM].rstrip("-") or _FALLBACK

    qs = model._default_manager.using(using)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)

    # One query: every slug that starts with the base. Cheap — the column is
    # unique-indexed and the prefix is anchored.
    taken = set(
        qs.filter(slug__startswith=base).values_list("slug", flat=True),
    )
    if base not in taken:
        return base

    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"
