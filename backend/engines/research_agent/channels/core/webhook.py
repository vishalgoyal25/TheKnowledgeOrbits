"""
engines/research_agent/channels/core/webhook.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ONE endpoint for every messaging channel.

    POST /api/v1/research/channels/<channel>/webhook/

The channel name is a path segment, resolved through the registry. Adapters do
not define URLs — platform #11's endpoint exists the moment its adapter file
does, with no core file edited and no route added.

WHAT THIS VIEW DOES, IN ORDER
    resolve adapter  →  verify signature  →  parse  →  enqueue  →  200

    That is all. No database writes, no HTTP calls, no business logic. Anything
    that could block belongs in the worker.

AUTHENTICATION
    This is the ONE endpoint exempt from the RBAC-decorator rule (CLAUDE.md).
    The adapter's `verify()` — an HMAC or shared secret from the provider — is
    its authentication, and it fails closed.

WHY ALMOST EVERYTHING RETURNS 200
    Providers retry non-2xx responses, often for hours. A 500 because of a
    payload we don't understand becomes the same payload arriving forever. So
    we answer 200 for anything we have decided to ignore, and reserve 4xx for
    "this request is not who it claims to be" (403) and "no such channel" (404).

    It is a plain sync Django view: never FastAPI, never ASGI, and never hosted
    on Vercel — it needs the ORM and the background worker.
"""

from __future__ import annotations

from dataclasses import asdict

import sentry_sdk
import structlog
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from engines.research_agent.channels.core import registry

logger = structlog.get_logger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class ChannelWebhookView(View):
    """
    Provider-facing endpoint. CSRF-exempt because the caller is a server, not a
    browser session — `verify()` is what proves the request is genuine.
    """

    def post(self, request, channel: str):
        adapter = registry.get(channel)

        if adapter is None:
            # Unknown or not-yet-built channel. A 404 is honest and stops a
            # misconfigured provider from retrying against a dead route.
            logger.warning(
                "channel.webhook.unknown_channel",
                channel=channel,
                known=registry.names(),
            )
            return JsonResponse({"detail": "Unknown channel."}, status=404)

        if not adapter.is_operational():
            # Kill switch off, or a credential missing. Acknowledge so the
            # provider stops retrying — being disabled is a decision, not a
            # fault, and a queue of retries would greet us when it is re-enabled.
            logger.info(
                "channel.webhook.not_operational",
                channel=channel,
                missing=getattr(adapter, "missing_config", lambda: None)(),
            )
            return HttpResponse(status=200)

        if not adapter.verify(request):
            logger.warning("channel.webhook.bad_signature", channel=channel)
            return JsonResponse({"detail": "Invalid signature."}, status=403)

        try:
            inbound = adapter.parse(request)
        except Exception as exc:
            # A parser crash is our bug. Swallow it with a 200 so the provider
            # does not replay the same payload indefinitely, and let Sentry
            # carry the alert instead.
            logger.error("channel.webhook.parse_error", channel=channel, error=str(exc))
            sentry_sdk.capture_exception(exc)
            return HttpResponse(status=200)

        if inbound is None:
            # A delivery receipt, an edit, a membership change — acknowledged
            # and ignored on purpose.
            return HttpResponse(status=200)

        # Deferred import: keeps `background_task` out of Django's startup path
        # for commands that never serve a webhook.
        from engines.research_agent.tasks.channel_task import handle_channel_update

        handle_channel_update(channel, asdict(inbound))

        logger.info(
            "channel.webhook.enqueued",
            channel=channel,
            provider_message_id=inbound.provider_message_id,
            kind=inbound.kind,
        )
        return HttpResponse(status=200)

    def get(self, request, channel: str):
        """
        Not a provider path — a human or an uptime check.

        Reports only whether the channel is known and operational. No
        credentials, no identities, nothing a scanner could use.
        """
        adapter = registry.get(channel)
        if adapter is None:
            return JsonResponse({"detail": "Unknown channel."}, status=404)
        return JsonResponse(
            {"channel": channel, "operational": adapter.is_operational()}, status=200
        )
