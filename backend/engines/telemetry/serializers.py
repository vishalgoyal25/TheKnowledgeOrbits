"""
Telemetry Engine Serializers

Input validation for the public read-beacon endpoint (POST /api/v1/telemetry/read/).

Threat model
────────────
This is the only UNAUTHENTICATED WRITE surface in the project. Anyone on the
internet can post to it, so this file is where hostile input stops. Everything
that reaches ContentRead.objects.create() has passed through here.
"""

import re

from rest_framework import serializers

from engines.telemetry.models import MAX_CONTENT_ID_LENGTH, ContentRead

# Slugs ("doctrine-of-basic-structure"), UUIDs
# ("550e8400-e29b-41d4-a716-446655440000") and numeric ids all fit this set.
# Anything else is junk or an injection attempt, and a public endpoint should
# not be storing 255 bytes of arbitrary attacker-chosen text on every request.
_CONTENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


class ContentReadSerializer(serializers.Serializer):  # type: ignore
    """
    Validates one read-beacon POST.

    Deliberately a plain Serializer, NOT a ModelSerializer
    ─────────────────────────────────────────────────────
    ContentRead has six fields. Exactly TWO may come from the client:

        content_type, content_id      <- client-supplied, validated here
        ip_hash                       <- derived server-side from X-Forwarded-For
        is_authenticated              <- derived server-side from request.user
        read_date                     <- derived server-side from the clock
        id                            <- generated

    A ModelSerializer would keep those three server-derived fields one careless
    `fields` edit away from being client-writable — and a caller who could set
    `is_authenticated` or `ip_hash` could forge readership and defeat the daily
    dedupe. Listing the accepted input explicitly makes that mistake impossible
    to make by accident: the fields are not merely excluded, they do not exist
    on this serializer.

    The choices and length cap are still imported from the model, so the model
    remains the single source of truth for what the values may be.

    This serializer never calls .save() — the view constructs the row so it can
    supply the server-derived fields. `create()`/`update()` are intentionally
    not implemented.
    """

    content_type = serializers.ChoiceField(
        choices=ContentRead.CONTENT_TYPE_CHOICES,
        help_text="Which kind of content was read",
    )

    content_id = serializers.CharField(
        max_length=MAX_CONTENT_ID_LENGTH,
        min_length=1,
        trim_whitespace=True,
        help_text="Slug or UUID of the content, as text",
    )

    def validate_content_id(self, value: str) -> str:
        """Reject anything outside the slug/UUID character set."""
        if not _CONTENT_ID_PATTERN.match(value):
            raise serializers.ValidationError(
                "May contain only letters, digits, hyphen, underscore or period."
            )
        return value
