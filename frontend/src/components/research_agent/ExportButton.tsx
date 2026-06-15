"use client";

import { useState } from "react";
import { FileText, FileDown, Loader2 } from "lucide-react";
import { buildExportUrl } from "@/lib/api/research-agent";

export interface ExportButtonProps {
  sessionId: string;
  disabled?: boolean;
}

type ExportFormat = "pdf" | "md";

interface ButtonState {
  loading: boolean;
  error: string | null;
}

const INITIAL_STATE: ButtonState = { loading: false, error: null };

export default function ExportButton({
  sessionId,
  disabled = false,
}: ExportButtonProps) {
  const [pdfState, setPdfState] = useState<ButtonState>(INITIAL_STATE);
  const [mdState, setMdState] = useState<ButtonState>(INITIAL_STATE);

  async function handleExport(format: ExportFormat) {
    const setState = format === "pdf" ? setPdfState : setMdState;
    setState({ loading: true, error: null });

    try {
      const url = buildExportUrl(sessionId, format);
      // Browser-native file download — no blob handling needed.
      // The backend sets Content-Disposition: attachment so the browser saves the file.
      window.location.href = url;

      // Small delay so the spinner is visible before the download dialog appears.
      await new Promise((r) => setTimeout(r, 800));
    } catch {
      setState({
        loading: false,
        error: `${format.toUpperCase()} export failed.`,
      });
      return;
    }

    setState(INITIAL_STATE);
  }

  const isDisabled = disabled || pdfState.loading || mdState.loading;

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-2">
        {/* PDF */}
        <button
          type="button"
          onClick={() => handleExport("pdf")}
          disabled={isDisabled}
          className={[
            "flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium",
            "transition-all duration-150 focus:outline-none",
            "focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2",
            isDisabled
              ? "border-gray-200 bg-gray-50 text-gray-400 cursor-not-allowed"
              : "border-gray-300 bg-white text-gray-700 hover:border-gray-400 hover:bg-gray-50",
          ].join(" ")}
        >
          {pdfState.loading ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin text-gray-400" />
          ) : (
            <FileText className="w-3.5 h-3.5 text-red-500" />
          )}
          Export PDF
        </button>

        {/* Markdown */}
        <button
          type="button"
          onClick={() => handleExport("md")}
          disabled={isDisabled}
          className={[
            "flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium",
            "transition-all duration-150 focus:outline-none",
            "focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2",
            isDisabled
              ? "border-gray-200 bg-gray-50 text-gray-400 cursor-not-allowed"
              : "border-gray-300 bg-white text-gray-700 hover:border-gray-400 hover:bg-gray-50",
          ].join(" ")}
        >
          {mdState.loading ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin text-gray-400" />
          ) : (
            <FileDown className="w-3.5 h-3.5 text-blue-500" />
          )}
          Export MD
        </button>
      </div>

      {/* Per-format error messages */}
      {pdfState.error && (
        <p className="text-[11px] text-red-500">{pdfState.error}</p>
      )}
      {mdState.error && (
        <p className="text-[11px] text-red-500">{mdState.error}</p>
      )}
    </div>
  );
}
