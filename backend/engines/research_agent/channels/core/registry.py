"""
engines/research_agent/channels/core/registry.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Name → adapter. The ONE place core is aware that adapters exist.

WHY THIS IS NOT A DICT
    A hand-maintained mapping would mean every new platform edits a core file —
    exactly what this architecture forbids. So the registry SCANS `channels/`
    for sibling packages, imports each one's `adapter` module, and registers
    any concrete ChannelAdapter it finds.

    Dropping in `channels/slack/adapter.py` registers Slack. No core file moves.
    Same pattern Django uses to discover apps.

WHO NEEDS IT
    The background worker holds only a `session_id`. It reads `session.channel`
    and must find the adapter that can deliver the result — there is no request
    object to carry one. The webhook needs the same lookup from a URL segment.

DISCOVERY IS LAZY
    Nothing scans at import time. Django imports this module during startup and
    during `migrate`; pulling in `requests`, env reads and HTTP clients there
    would be wasteful and could fail a management command for no reason.

ONE BROKEN ADAPTER MUST NOT TAKE DOWN THE REST
    An adapter that raises on import is logged, reported to Sentry, and skipped.
    Telegram staying up while WhatsApp is misconfigured is the correct
    behaviour — channels are independent by design.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil

import sentry_sdk
import structlog

from engines.research_agent.channels.core.adapter import ChannelAdapter
from engines.research_agent.constants import SessionChannel

logger = structlog.get_logger(__name__)

# Packages under channels/ that are not adapters.
_NOT_ADAPTERS = {"core"}

_adapters: dict[str, ChannelAdapter] = {}
_discovered = False


def discover(force: bool = False) -> dict[str, ChannelAdapter]:
    """Scan `channels/` and register every concrete adapter. Idempotent."""
    global _discovered

    if _discovered and not force:
        return _adapters

    _adapters.clear()

    from engines.research_agent import channels as channels_pkg

    for module_info in pkgutil.iter_modules(channels_pkg.__path__):
        if not module_info.ispkg or module_info.name in _NOT_ADAPTERS:
            continue

        dotted = f"{channels_pkg.__name__}.{module_info.name}.adapter"

        try:
            module = importlib.import_module(dotted)
        except ModuleNotFoundError:
            # A channel package with no adapter yet. Expected for work in
            # progress and for held channels — not an error.
            logger.debug("channel.registry.no_adapter", package=module_info.name)
            continue
        except Exception as exc:
            # A real failure: syntax error, bad import, config blowing up at
            # module scope. Skip this adapter; leave the others working.
            logger.error(
                "channel.registry.import_failed",
                package=module_info.name,
                error=str(exc),
            )
            sentry_sdk.capture_exception(exc)
            continue

        _register_from_module(module, module_info.name)

    _discovered = True
    logger.info("channel.registry.discovered", channels=sorted(_adapters))
    return _adapters


def _register_from_module(module, package_name: str) -> None:
    """Find concrete ChannelAdapter subclasses in a module and register them."""
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if not issubclass(obj, ChannelAdapter) or obj is ChannelAdapter:
            continue
        if inspect.isabstract(obj):
            continue
        # Only classes DEFINED here — skip ones merely imported into scope,
        # or an adapter would register twice under two package names.
        if obj.__module__ != module.__name__:
            continue

        try:
            instance = obj()
        except Exception as exc:
            logger.error(
                "channel.registry.instantiation_failed",
                package=package_name,
                adapter=obj.__name__,
                error=str(exc),
            )
            sentry_sdk.capture_exception(exc)
            continue

        name = getattr(instance, "name", None)

        # An adapter whose name is not a known SessionChannel would create
        # sessions the DB CHECK constraint rejects. Refuse it here, where the
        # error is obvious, rather than at the first user message.
        if name not in SessionChannel.ALL:
            logger.error(
                "channel.registry.unknown_channel_name",
                package=package_name,
                adapter=obj.__name__,
                name=name,
                allowed=list(SessionChannel.ALL),
            )
            continue

        if name in _adapters:
            logger.error(
                "channel.registry.duplicate_channel",
                name=name,
                existing=type(_adapters[name]).__name__,
                rejected=obj.__name__,
            )
            continue

        _adapters[name] = instance
        logger.info("channel.registry.registered", channel=name, adapter=obj.__name__)


# ──────────────────────────────────────────────────────────────────────────────
# PUBLIC
# ──────────────────────────────────────────────────────────────────────────────


def get(name: str) -> ChannelAdapter | None:
    """
    The adapter for a channel, or None if there isn't one.

    None is a normal answer — an unknown URL segment, or a channel whose
    adapter has not been built yet. Callers turn it into a 404, never a 500.
    """
    return discover().get(name)


def all_adapters() -> dict[str, ChannelAdapter]:
    """Every registered adapter, keyed by channel name."""
    return dict(discover())


def names() -> list[str]:
    """Registered channel names, sorted."""
    return sorted(discover())


def operational_names() -> list[str]:
    """
    Channels that are registered AND currently usable — flag on, credentials
    present. Registration means the code exists; operational means it can send.
    """
    return sorted(
        name for name, adapter in discover().items() if adapter.is_operational()
    )


def describe() -> list[dict]:
    """Non-sensitive snapshot of every adapter, for health checks and logs."""
    return [adapter.describe() for _, adapter in sorted(discover().items())]
