"""
engines/research_agent/apps.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Research Agent engine — AppConfig.
7-agent LangGraph system: Supervisor → Planner → Search → Research →
Verification → Report Generator → Reflection
"""

from django.apps import AppConfig


class ResearchAgentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "engines.research_agent"
    label = "research_agent"
    verbose_name = "Research Agent"

    def ready(self) -> None:
        # Import the background task module so its @background decorator runs and
        # REGISTERS the task in every process that loads this app — including the
        # `process_tasks` worker. Without this, the worker can't find/run the
        # queued task (it only knows tasks that were imported during startup).
        # The module's heavy deps are imported lazily inside the task body, so
        # this import stays cheap.
        from engines.research_agent.tasks import research_task  # noqa: F401
        from engines.research_agent.tasks import evaluation_task  # noqa: F401
