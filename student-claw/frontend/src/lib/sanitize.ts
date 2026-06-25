"use client";

/**
 * Safe rendering of Agnes's Telegram-HTML responses.
 *
 * Agnes is constrained (server-side prompt) to emit only Telegram-supported
 * tags, but we never trust that on the client: every response is run through
 * DOMPurify with a strict allow-list before `dangerouslySetInnerHTML`. Links
 * are forced to open in a new tab with `rel="noopener noreferrer"`.
 */

import DOMPurify from "dompurify";

const ALLOWED_TAGS = [
  "b",
  "strong",
  "i",
  "em",
  "u",
  "s",
  "code",
  "pre",
  "a",
  "br",
];

let hookRegistered = false;

function ensureHook(): void {
  if (hookRegistered || typeof window === "undefined") return;
  DOMPurify.addHook("afterSanitizeAttributes", (node) => {
    if (node.tagName === "A") {
      node.setAttribute("target", "_blank");
      node.setAttribute("rel", "noopener noreferrer");
    }
  });
  hookRegistered = true;
}

/** Sanitize an Agnes HTML string down to the Telegram tag subset. */
export function sanitizeTelegramHtml(html: string): string {
  if (typeof window === "undefined") return "";
  ensureHook();
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR: ["href", "target", "rel"],
    ALLOWED_URI_REGEXP: /^(?:https?:|mailto:|tg:)/i,
  });
}
