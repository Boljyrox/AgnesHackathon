/**
 * AES-256-GCM at-rest encryption for the Google refresh token (blueprint §6.5).
 *
 * Blob layout (must match backend app/core/security.py):
 *   base64( IV(12 bytes) || ciphertext || GCM tag(16 bytes) )
 *
 * The IV is randomly generated per call (never reused) and the authentication
 * tag is appended to the ciphertext, so there is no separate tag field to leak.
 * Node-only (uses node:crypto); call from `runtime = "nodejs"` routes.
 */

import { createCipheriv, randomBytes } from "node:crypto";

import { ENCRYPTION_KEY } from "@/lib/env";

const IV_LEN = 12; // 96-bit GCM nonce
const TAG_LEN = 16;

function resolveKey(): Buffer {
  if (!ENCRYPTION_KEY) {
    throw new Error("ENCRYPTION_KEY is not configured.");
  }
  const key =
    ENCRYPTION_KEY.length === 64
      ? Buffer.from(ENCRYPTION_KEY, "hex")
      : Buffer.from(ENCRYPTION_KEY, "base64");
  if (key.length !== 32) {
    throw new Error("ENCRYPTION_KEY must decode to exactly 32 bytes (AES-256).");
  }
  return key;
}

/** Encrypt a plaintext secret → base64(IV || ciphertext || tag). */
export function encryptSecret(plaintext: string): string {
  const iv = randomBytes(IV_LEN);
  const cipher = createCipheriv("aes-256-gcm", resolveKey(), iv);
  const ciphertext = Buffer.concat([
    cipher.update(plaintext, "utf8"),
    cipher.final(),
  ]);
  const tag = cipher.getAuthTag();
  // Layout: IV || ciphertext || tag  (tag is exactly TAG_LEN bytes).
  return Buffer.concat([iv, ciphertext, tag]).toString("base64");
}

export const GCM_TAG_LEN = TAG_LEN;
