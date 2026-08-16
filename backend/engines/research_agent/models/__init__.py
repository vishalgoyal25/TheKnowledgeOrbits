# engines/research_agent/models/__init__.py
# Models implemented in Phase 2.

from engines.research_agent.models.research_session import ResearchSession
from engines.research_agent.models.research_report import ResearchReport
from engines.research_agent.models.agent_execution_log import AgentExecutionLog
from engines.research_agent.models.evaluation_result import EvaluationResult
from engines.research_agent.models.agent_state_snapshot import AgentStateSnapshot

# Channel tables (FEATURE_WHATSAPP.md). They declare
# `app_label = "research_agent"` and live under channels/, which Django does
# NOT auto-import — so they are re-exported here purely so `makemigrations`
# and the app registry can find them. Imported LAST: they reference
# ResearchSession, which must already be registered above.
from engines.research_agent.channels.whatsapp.models import (
    WhatsAppContact,
    WhatsAppMessage,
    ReportDelivery,
)

__all__ = [
    "ResearchSession",
    "ResearchReport",
    "AgentExecutionLog",
    "EvaluationResult",
    "AgentStateSnapshot",
    # WhatsApp channel
    "WhatsAppContact",
    "WhatsAppMessage",
    "ReportDelivery",
]
