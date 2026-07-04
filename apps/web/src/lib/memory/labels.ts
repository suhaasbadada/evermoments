import type { VerificationStatus } from "@/types/memory";

export const VERIFICATION_LABELS: Record<VerificationStatus, string> = {
  unverified: "Unverified",
  confirmed: "Confirmed",
  incorrect: "Incorrect",
  needs_check: "Needs Checking",
  safety_critical: "Safety Critical",
};

export const VERIFICATION_BADGE_CLASSES: Record<VerificationStatus, string> = {
  unverified: "text-amber-700 bg-amber-100 border-amber-300",
  confirmed: "text-emerald-700 bg-emerald-100 border-emerald-300",
  incorrect: "text-slate-500 bg-slate-100 border-slate-300",
  needs_check: "text-amber-700 bg-amber-100 border-amber-300",
  safety_critical: "text-red-700 bg-red-100 border-red-300",
};

// The four caregiver actions. "Duplicate" from the original mock was folded
// into "Incorrect" per team decision — Japit's verification.status enum
// (§6.1) never had a separate duplicate value.
export const VERIFICATION_ACTIONS: VerificationStatus[] = [
  "confirmed",
  "needs_check",
  "incorrect",
  "safety_critical",
];
