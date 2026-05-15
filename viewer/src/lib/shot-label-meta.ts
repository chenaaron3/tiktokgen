import type { IdentifiedShot, LabelConfidence, VerifiedBy, VlmClip } from "@/types/vlm"

export function clipHasGptLabel(clip: VlmClip): boolean {
  return (clip.identifiedShots ?? []).some((shot) => shot.verifiedBy === "gpt")
}

export function formatShotTimelineTitle(shot: IdentifiedShot): string {
  const tag = shot.vlmTag ?? "?"
  const confidence = shot.labelConfidence ?? "?"
  const verified = shot.verifiedBy ?? "?"
  return `${tag} • ${confidence} • ${verified}`
}

export function confidenceBadgeClass(confidence: LabelConfidence | undefined): string {
  switch (confidence) {
    case "high":
      return "border-emerald-500/40 bg-emerald-500/15 text-emerald-300"
    case "medium":
      return "border-amber-500/40 bg-amber-500/15 text-amber-300"
    case "low":
      return "border-orange-500/40 bg-orange-500/15 text-orange-300"
    default:
      return "border-zinc-600 bg-zinc-800/80 text-zinc-400"
  }
}

export function formatVerifiedBy(verifiedBy: VerifiedBy | undefined): string {
  if (verifiedBy === "gpt") return "GPT"
  if (verifiedBy === "twelvelabs") return "TwelveLabs"
  return "—"
}
