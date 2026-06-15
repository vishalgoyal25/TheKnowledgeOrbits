"""
engines/research_agent/services/export_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Export a finished report as Markdown or PDF.

  - Markdown: always available (plain text assembly).
  - PDF: rendered with WeasyPrint (markdown → HTML → PDF). WeasyPrint is
    production-only (requirements/prod.txt) and needs system libs that are often
    missing on local Windows — so PDF export FAILS GRACEFULLY there (raises
    ExportError → the view returns 503) while Markdown still works.

External image URLs are STRIPPED before PDF rendering (Risk #50) so WeasyPrint
never makes slow/failing external HTTP calls during render.
"""

from __future__ import annotations

import re

import structlog

logger = structlog.get_logger(__name__)

# Strip markdown image embeds that point at external URLs (Risk #50).
_EXTERNAL_IMG_RE = re.compile(r"!\[[^\]]*\]\(\s*https?://[^)]+\)")

_PDF_CSS = """
  body { font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.5;
         color: #1a1a1a; max-width: 760px; margin: 24px auto; padding: 0 16px; }
  h1 { font-size: 22px; border-bottom: 2px solid #2563eb; padding-bottom: 6px; }
  h2 { font-size: 17px; color: #1e3a8a; margin-top: 20px; }
  .meta { color: #555; font-size: 12px; margin-bottom: 16px; }
  ul { margin: 6px 0; } li { margin: 3px 0; }
  .sources { font-size: 12px; color: #444; }
"""


class ExportError(Exception):
    """Raised when export can't be produced (not found / PDF unavailable)."""

    pass


class ExportService:
    def export_markdown(self, session_id: str) -> tuple[str, str]:
        """Returns (filename, markdown_text)."""
        report = self._load_report(session_id)
        return self._filename(session_id, "md"), self._compose_markdown(report)

    def export_pdf(self, session_id: str) -> tuple[str, bytes]:
        """Returns (filename, pdf_bytes). Raises ExportError if WeasyPrint absent."""
        report = self._load_report(session_id)
        md = self._strip_external_images(self._compose_markdown(report))
        html = self._md_to_html(md)
        pdf = self._html_to_pdf(html)
        return self._filename(session_id, "pdf"), pdf

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE
    # ──────────────────────────────────────────────────────────────────────────
    def _load_report(self, session_id: str):
        from engines.research_agent.models.research_report import ResearchReport

        report = (
            ResearchReport.objects.filter(session_id=session_id)
            .select_related("session")
            .first()
        )
        if report is None:
            raise ExportError("report_not_found")
        return report

    def _compose_markdown(self, report) -> str:
        confidence = (
            f"{round(report.confidence_score * 100)}%"
            if report.confidence_score is not None
            else "pending"
        )
        query = getattr(report.session, "query", "Research Report")

        lines = [
            f"# {query}",
            "",
            f"*Research Confidence: {confidence} · {report.word_count} words*",
            "",
            "## Executive Summary",
            "",
            report.executive_summary or "(none)",
            "",
            "## Full Report",
            "",
            report.full_report or "(none)",
            "",
            "## Sources",
            "",
        ]
        for i, s in enumerate(report.sources or [], start=1):
            title = s.get("title") or "Untitled"
            url = s.get("url") or ""
            lines.append(f"{i}. [{title}]({url})")
        return "\n".join(lines)

    def _strip_external_images(self, md: str) -> str:
        return _EXTERNAL_IMG_RE.sub("", md)

    def _md_to_html(self, md: str) -> str:
        try:
            from markdown_it import MarkdownIt

            body = MarkdownIt().render(md)
        except Exception:
            # Fallback: very basic — wrap as preformatted text.
            body = "<pre>" + (md.replace("<", "&lt;").replace(">", "&gt;")) + "</pre>"
        return f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{_PDF_CSS}</style></head><body>{body}</body></html>"

    def _html_to_pdf(self, html: str) -> bytes:
        try:
            from weasyprint import HTML
        except Exception as exc:
            logger.warning("research_agent.export.pdf_unavailable", error=str(exc))
            raise ExportError("pdf_unavailable")
        try:
            return HTML(string=html).write_pdf()
        except Exception as exc:
            logger.error("research_agent.export.pdf_render_failed", error=str(exc))
            raise ExportError("pdf_render_failed")

    @staticmethod
    def _filename(session_id: str, ext: str) -> str:
        return f"research-{session_id[:8]}.{ext}"


# Module-level singleton.
export_service = ExportService()
