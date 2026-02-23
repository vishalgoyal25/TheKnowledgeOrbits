/**
 * @file GlobalErrorBoundary.tsx
 * @description React Error Boundary that wraps the entire app layout.
 *
 * Catches any unhandled JavaScript errors thrown during rendering, in lifecycle
 * methods, or in constructors of any child component tree. Instead of a blank
 * white screen ("WSOD"), the user sees a polished recovery UI.
 *
 * ## Implementation note
 * Error Boundaries must be **class components** — React does not yet support
 * them as function components. This is the only class component in the project.
 */

"use client";

import { Component, ErrorInfo, ReactNode } from "react";
import * as Sentry from "@sentry/nextjs";
import { createLogger } from "@/lib/logger";

const logger = createLogger("ErrorBoundary");

// ─── Types ───────────────────────────────────────────────────────────────────

interface Props {
    /** The component subtree to protect. */
    children: ReactNode;
    /**
     * Optional custom fallback UI. Receives the caught error so you can display
     * context-specific messages. Defaults to the built-in recovery screen.
     */
    fallback?: (error: Error, reset: () => void) => ReactNode;
}

interface State {
    /** Whether an error has been caught. */
    hasError: boolean;
    /** The caught error object, if any. */
    error: Error | null;
}

// ─── Component ───────────────────────────────────────────────────────────────

/**
 * Global Error Boundary — wraps the root layout to prevent white screens.
 *
 * @example
 * // In layout.tsx:
 * <GlobalErrorBoundary>
 *   <AuthProvider>...</AuthProvider>
 * </GlobalErrorBoundary>
 */
export class GlobalErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false, error: null };
        this.handleReset = this.handleReset.bind(this);
    }

    // ── Lifecycle ──────────────────────────────────────────────────────────────

    static getDerivedStateFromError(error: Error): State {
        // Update state so the next render shows the fallback UI
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, info: ErrorInfo): void {
        // Log structured error details via our professional logger
        logger.error("Unhandled UI exception caught by GlobalErrorBoundary", {
            message: error.message,
            stack: error.stack,
            componentStack: info.componentStack,
        });

        // Forward to Sentry — captures the full stack trace + React component tree
        Sentry.captureException(error, {
            extra: {
                componentStack: info.componentStack,
            },
        });
    }

    // ── Helpers ────────────────────────────────────────────────────────────────

    /** Clears the error state so the user can attempt to recover. */
    handleReset(): void {
        this.setState({ hasError: false, error: null });
    }

    // ── Render ─────────────────────────────────────────────────────────────────

    render(): ReactNode {
        if (this.state.hasError && this.state.error) {
            // If a custom fallback was provided, use it
            if (this.props.fallback) {
                return this.props.fallback(this.state.error, this.handleReset);
            }

            // Otherwise render the default recovery screen
            return (
                <DefaultErrorFallback
                    error={this.state.error}
                    onReset={this.handleReset}
                />
            );
        }

        return this.props.children;
    }
}

// ─── Default Fallback UI ─────────────────────────────────────────────────────

interface FallbackProps {
    error: Error;
    onReset: () => void;
}

/**
 * Renders a polished, branded "Something went wrong" recovery screen.
 * Includes the error message for developer context and a retry button.
 */
function DefaultErrorFallback({ error, onReset }: FallbackProps) {
    const isDev = process.env.NODE_ENV !== "production";

    return (
        <div
            role="alert"
            style={{
                minHeight: "100vh",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                background: "linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%)",
                color: "#f8fafc",
                fontFamily: "Inter, system-ui, sans-serif",
                padding: "2rem",
                textAlign: "center",
            }}
        >
            {/* Icon */}
            <div
                style={{
                    width: 80,
                    height: 80,
                    borderRadius: "50%",
                    background: "rgba(220, 38, 38, 0.15)",
                    border: "2px solid rgba(220, 38, 38, 0.4)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "2.5rem",
                    marginBottom: "1.5rem",
                }}
            >
                ⚠️
            </div>

            {/* Heading */}
            <h1
                style={{
                    fontSize: "2rem",
                    fontWeight: 700,
                    marginBottom: "0.75rem",
                    background: "linear-gradient(90deg, #f8fafc, #a78bfa)",
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                }}
            >
                Something Went Wrong
            </h1>

            <p
                style={{
                    color: "#94a3b8",
                    maxWidth: 480,
                    lineHeight: 1.6,
                    marginBottom: "2rem",
                    fontSize: "1rem",
                }}
            >
                An unexpected error occurred. Our team has been notified. You can try
                refreshing the page or clicking the button below to recover.
            </p>

            {/* Dev-only: show the raw error message */}
            {isDev && (
                <details
                    style={{
                        background: "rgba(220, 38, 38, 0.1)",
                        border: "1px solid rgba(220, 38, 38, 0.3)",
                        borderRadius: 8,
                        padding: "1rem",
                        maxWidth: 600,
                        width: "100%",
                        marginBottom: "2rem",
                        textAlign: "left",
                        cursor: "pointer",
                    }}
                >
                    <summary
                        style={{ color: "#fca5a5", fontWeight: 600, marginBottom: "0.5rem" }}
                    >
                        🛠 Developer Details (dev only)
                    </summary>
                    <pre
                        style={{
                            color: "#fca5a5",
                            fontSize: "0.8rem",
                            whiteSpace: "pre-wrap",
                            wordBreak: "break-word",
                            marginTop: "0.5rem",
                        }}
                    >
                        {error.message}
                        {"\n\n"}
                        {error.stack}
                    </pre>
                </details>
            )}

            {/* Action buttons */}
            <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", justifyContent: "center" }}>
                <button
                    onClick={onReset}
                    style={{
                        background: "linear-gradient(135deg, #7C3AED, #4F46E5)",
                        color: "#fff",
                        border: "none",
                        borderRadius: 8,
                        padding: "0.75rem 1.75rem",
                        fontSize: "1rem",
                        fontWeight: 600,
                        cursor: "pointer",
                        transition: "opacity 0.2s",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.opacity = "0.85")}
                    onMouseLeave={(e) => (e.currentTarget.style.opacity = "1")}
                >
                    Try Again
                </button>
                <button
                    onClick={() => (window.location.href = "/")}
                    style={{
                        background: "transparent",
                        color: "#94a3b8",
                        border: "1px solid rgba(148,163,184,0.4)",
                        borderRadius: 8,
                        padding: "0.75rem 1.75rem",
                        fontSize: "1rem",
                        fontWeight: 600,
                        cursor: "pointer",
                        transition: "border-color 0.2s, color 0.2s",
                    }}
                    onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = "rgba(148,163,184,0.8)";
                        e.currentTarget.style.color = "#f1f5f9";
                    }}
                    onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = "rgba(148,163,184,0.4)";
                        e.currentTarget.style.color = "#94a3b8";
                    }}
                >
                    Go to Home
                </button>
            </div>
        </div>
    );
}
