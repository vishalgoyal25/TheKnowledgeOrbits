"use client";

/**
 * engines/social/share-button.tsx — Share popover (Phase H).
 *
 * Platforms: Copy Link · WhatsApp · Twitter/X · Telegram
 *
 * Auth rules:
 *   - Copying / opening share URLs → works for ALL users, authenticated or not.
 *   - POST /api/v1/social/shares/  → fire-and-forget, silently skipped for guests.
 *     (share_count increments only when the user is logged in — count is a bonus,
 *      not a gate on the actual sharing action.)
 */

import {
  Check,
  Link,
  MessageCircle,
  Send,
  Share2,
  Twitter,
} from "lucide-react";
import { useCallback, useState } from "react";

import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/lib/auth/useAuth";
import { type ContentType, type Platform, logShare } from "@/lib/api/social";
import { cn } from "@/lib/utils";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ShareButtonProps {
  contentType: ContentType;
  contentId: string;
  /** Full canonical URL to share (e.g. https://theknowledgeorbits.com/daily-ca/…) */
  shareUrl: string;
  /** Article / quiz title used in share message body. */
  shareTitle: string;
  /** Optional: share count to display on the trigger button. */
  shareCount?: number;
  className?: string;
}

// ── Share URL builders ────────────────────────────────────────────────────────

function buildWhatsAppUrl(shareUrl: string, shareTitle: string): string {
  const text = encodeURIComponent(`${shareTitle}\n${shareUrl}`);
  return `https://api.whatsapp.com/send?text=${text}`;
}

function buildTwitterUrl(shareUrl: string, shareTitle: string): string {
  const text = encodeURIComponent(shareTitle);
  const url = encodeURIComponent(shareUrl);
  return `https://twitter.com/intent/tweet?text=${text}&url=${url}`;
}

function buildTelegramUrl(shareUrl: string, shareTitle: string): string {
  const text = encodeURIComponent(shareTitle);
  const url = encodeURIComponent(shareUrl);
  return `https://t.me/share/url?url=${url}&text=${text}`;
}

// ── Platform option config ────────────────────────────────────────────────────

interface PlatformOption {
  platform: Platform;
  label: string;
  icon: React.ReactNode;
  colorClass: string;
  getUrl: ((shareUrl: string, shareTitle: string) => string) | null; // null = copy
}

const PLATFORM_OPTIONS: PlatformOption[] = [
  {
    platform: "copy_link",
    label: "Copy Link",
    icon: <Link className="h-4 w-4" />,
    colorClass: "text-gray-700 hover:bg-gray-100",
    getUrl: null,
  },
  {
    platform: "whatsapp",
    label: "WhatsApp",
    icon: <MessageCircle className="h-4 w-4" />,
    colorClass: "text-green-700 hover:bg-green-50",
    getUrl: buildWhatsAppUrl,
  },
  {
    platform: "twitter",
    label: "Twitter / X",
    icon: <Twitter className="h-4 w-4" />,
    colorClass: "text-sky-600 hover:bg-sky-50",
    getUrl: buildTwitterUrl,
  },
  {
    platform: "telegram",
    label: "Telegram",
    icon: <Send className="h-4 w-4" />,
    colorClass: "text-blue-600 hover:bg-blue-50",
    getUrl: buildTelegramUrl,
  },
];

// ── Component ─────────────────────────────────────────────────────────────────

export function ShareButton({
  contentType,
  contentId,
  shareUrl,
  shareTitle,
  shareCount,
  className,
}: ShareButtonProps) {
  const { isAuthenticated } = useAuth();
  const { toast } = useToast();

  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  /** Fire-and-forget share log — never blocks the UI action. */
  const logShareQuiet = useCallback(
    async (platform: Platform) => {
      if (!isAuthenticated) return; // guests: no log, no error
      try {
        await logShare(contentType, contentId, platform);
      } catch {
        // Silently ignore — share already happened for the user
      }
    },
    [isAuthenticated, contentType, contentId],
  );

  const handleCopyLink = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      toast({
        title: "Link copied!",
        description: "Share link copied to clipboard.",
      });
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API blocked (e.g. non-HTTPS iframe) — fallback
      toast({
        title: "Could not copy",
        description: "Please copy the URL from your browser address bar.",
        variant: "destructive",
      });
    }
    logShareQuiet("copy_link");
    setOpen(false);
  }, [shareUrl, toast, logShareQuiet]);

  const handlePlatform = useCallback(
    (option: PlatformOption) => {
      if (!option.getUrl) {
        handleCopyLink();
        return;
      }
      const url = option.getUrl(shareUrl, shareTitle);
      window.open(url, "_blank", "noopener,noreferrer");
      logShareQuiet(option.platform);
      setOpen(false);
    },
    [shareUrl, shareTitle, handleCopyLink, logShareQuiet],
  );

  // ── Compact count helper ─────────────────────────────────────────────────

  const countLabel =
    shareCount !== undefined && shareCount > 0
      ? shareCount >= 1000
        ? `${(shareCount / 1000).toFixed(1).replace(/\.0$/, "")}k`
        : String(shareCount)
      : null;

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          aria-label="Share"
          className={cn(
            "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium transition-colors select-none",
            open
              ? "text-indigo-600 bg-indigo-50"
              : "text-gray-500 hover:text-indigo-600 hover:bg-indigo-50",
            className,
          )}
        >
          <Share2 className="h-4 w-4" />
          <span className="hidden sm:inline">{countLabel ?? "Share"}</span>
          {countLabel && <span className="sm:hidden">{countLabel}</span>}
        </button>
      </PopoverTrigger>

      <PopoverContent align="start" sideOffset={8} className="w-48 p-1.5">
        <p className="px-2 pb-1.5 pt-0.5 text-xs font-semibold text-gray-400 uppercase tracking-wide">
          Share via
        </p>

        {PLATFORM_OPTIONS.map((option) => (
          <button
            key={option.platform}
            onClick={() => handlePlatform(option)}
            className={cn(
              "flex w-full items-center gap-2.5 rounded-md px-2 py-2 text-sm font-medium transition-colors",
              option.colorClass,
            )}
          >
            {option.platform === "copy_link" && copied ? (
              <Check className="h-4 w-4 text-green-600" />
            ) : (
              option.icon
            )}
            <span>
              {option.platform === "copy_link" && copied
                ? "Copied!"
                : option.label}
            </span>
          </button>
        ))}
      </PopoverContent>
    </Popover>
  );
}
