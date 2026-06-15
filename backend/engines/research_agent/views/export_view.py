"""
engines/research_agent/views/export_view.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GET /api/v1/research/export/<session_id>/?format=pdf|md

Returns the report as a downloadable Markdown or PDF file. Plain Django View
(clean binary/file responses; the unguessable session UUID is the capability
token, consistent with the stream/cancel endpoints).
"""

from __future__ import annotations

import structlog
from django.http import HttpResponse, JsonResponse
from django.views import View

from engines.research_agent.services.export_service import export_service, ExportError

logger = structlog.get_logger(__name__)


class ExportView(View):
    def get(self, request, session_id: str):
        fmt = (request.GET.get("format") or "md").lower()
        # PDF export returns bytes; Markdown returns str — both valid HttpResponse bodies.
        content: bytes | str
        try:
            if fmt == "pdf":
                filename, content = export_service.export_pdf(session_id)
                response = HttpResponse(content, content_type="application/pdf")
            else:
                filename, content = export_service.export_markdown(session_id)
                response = HttpResponse(
                    content, content_type="text/markdown; charset=utf-8"
                )
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            logger.info(
                "research_agent.export.served", session_id=session_id, format=fmt
            )
            return response
        except ExportError as exc:
            reason = str(exc)
            status = 404 if reason == "report_not_found" else 503
            detail = {
                "report_not_found": "No report found for this session.",
                "pdf_unavailable": "PDF export is not available on this server (Markdown works).",
                "pdf_render_failed": "PDF rendering failed; try Markdown.",
            }.get(reason, "Export failed.")
            return JsonResponse({"detail": detail}, status=status)
