/**
 * POST /api/projects/link  — Phase 3 of onboarding (§4.1).
 *
 * Flow:
 *   1. Authenticate the session.
 *   2. Validate the submitted project_key shape.
 *   3. Mint a cryptographically random 32-byte hex link_token with a strict
 *      15-minute expiry (computed server-side here).
 *   4. Hand the token + project_key to FastAPI, which validates the key against
 *      the projects table, confirms the user's telegram_username is part of the
 *      group, and persists the row into project_link_tokens (single-use).
 *   5. Return the token + instructions for the user to run `/verify <token>` in
 *      their Telegram group.
 *
 * Token generation lives here (BFF) per the module spec; persistence/uniqueness
 * enforcement stays in FastAPI, which owns the project_link_tokens table.
 */

import { randomBytes } from "node:crypto";

import { NextResponse } from "next/server";
import { z } from "zod";

import { requireSession } from "@/lib/auth";
import { backendJson, BackendError } from "@/lib/backend";
import { BACKEND_ROUTES, LINK_TOKEN_TTL_SECONDS } from "@/lib/env";
import { errorJson } from "@/lib/responses";
import type { ProjectLinkResponse } from "@/lib/types";

export const runtime = "nodejs";

const LinkSchema = z.object({
  // e.g. "SC-4f8a2b9e1c3d7f0a" — prefix + 16 hex; allow some slack for input.
  project_key: z
    .string()
    .trim()
    .min(8)
    .max(64)
    .regex(/^[A-Za-z0-9-]+$/, "invalid project key format"),
});

export async function POST(req: Request): Promise<NextResponse> {
  const auth = await requireSession();
  if ("response" in auth) return auth.response;

  const body = await req.json().catch(() => null);
  const parsed = LinkSchema.safeParse(body);
  if (!parsed.success) {
    return errorJson(400, "invalid_request", "A valid project key is required.");
  }

  // Cryptographically secure single-use token (32 bytes → 64 hex chars, §4.1).
  const token = randomBytes(32).toString("hex");
  const expiresAt = new Date(Date.now() + LINK_TOKEN_TTL_SECONDS * 1000).toISOString();

  try {
    await backendJson<{ ok: true }>({
      method: "POST",
      path: BACKEND_ROUTES.projectLink,
      bearer: auth.accessToken,
      body: {
        project_key: parsed.data.project_key,
        token,
        expires_at: expiresAt,
      },
    });

    const payload: ProjectLinkResponse = {
      verification_required: true,
      token,
      expires_at: expiresAt,
      instructions: `Send /verify ${token} in your Telegram group within 15 minutes.`,
    };
    return NextResponse.json(payload, { status: 200 });
  } catch (err) {
    if (err instanceof BackendError) {
      switch (err.status) {
        case 404:
          return errorJson(404, "project_not_found", "No project matches that key.");
        case 409:
          return errorJson(409, "already_linked", "You are already linked to this project.");
        case 422:
          return errorJson(
            422,
            "telegram_username_required",
            "Add your Telegram username to your account before linking.",
          );
        case 401:
          return errorJson(401, "unauthorized");
        default:
          return errorJson(502, "upstream_error");
      }
    }
    console.error("[projects/link] unexpected error:", err);
    return errorJson(500, "internal_error");
  }
}
