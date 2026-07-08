import type { ApiShowcaseDetail } from "@/lib/api";

/**
 * Seed fallback for story pages, mirroring the showcase-seed pattern in
 * cases.ts: real pipeline output, statically mirrored so a published
 * product's story survives the API being down (or its database resetting
 * on the free hosting tier). Keyed by PTP number.
 */
export const SEED_STORIES: Record<number, ApiShowcaseDetail> = {};
