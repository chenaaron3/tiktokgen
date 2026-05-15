import type { RenderBeat, ShotMatch, ShotMatchAssignment, ShotRef } from "@/types/vlm"

export function findShotMatchAssignment(
  shotMatch: ShotMatch | null | undefined,
  sentenceId: string,
): ShotMatchAssignment | null {
  if (!shotMatch?.assignments?.length) return null
  return shotMatch.assignments.find((a) => a.sentenceId === sentenceId) ?? null
}

export function findShotMatchRef(
  shotMatch: ShotMatch | null | undefined,
  clipId: string,
  shotId: string,
  sentenceId?: string,
): ShotRef | null {
  if (!shotMatch?.assignments?.length) return null
  const pools = sentenceId
    ? [findShotMatchAssignment(shotMatch, sentenceId)].filter(Boolean)
    : shotMatch.assignments
  for (const assignment of pools) {
    const hit = assignment!.shots.find((s) => s.clipId === clipId && s.shotId === shotId)
    if (hit) return hit
  }
  return null
}

export function findShotMatchReasoning(
  shotMatch: ShotMatch | null | undefined,
  clipId: string,
  shotId: string,
  sentenceId?: string,
): string | null {
  return findShotMatchRef(shotMatch, clipId, shotId, sentenceId)?.reasoning ?? null
}

export function shotMatchReasoningForBeat(
  shotMatch: ShotMatch | null | undefined,
  beat: RenderBeat | null,
): string | null {
  if (!beat) return null
  return findShotMatchReasoning(shotMatch, beat.clipId, beat.shotId, beat.sentenceId)
}
