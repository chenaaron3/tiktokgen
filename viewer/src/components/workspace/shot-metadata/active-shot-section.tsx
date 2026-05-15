import { HEADER_BODY_GAP } from "@/components/workspace/shot-metadata/constants"
import { ActiveShotMetadata } from "@/components/workspace/shot-metadata/active-shot-metadata"
import { SectionTitle } from "@/components/workspace/shot-metadata/primitives"
import { cn } from "@/lib/utils"
import type { IdentifiedShot } from "@/types/vlm"

export function ActiveShotSection({
  activeShot,
  emptyMessage,
  matchReasoning,
}: {
  activeShot: IdentifiedShot | null
  emptyMessage: string
  matchReasoning?: string | null
}) {
  return (
    <section className="min-w-0">
      <SectionTitle>Active shot @ playhead</SectionTitle>
      {activeShot ? (
        <ActiveShotMetadata shot={activeShot} matchReasoning={matchReasoning} />
      ) : (
        <p className={cn(HEADER_BODY_GAP, "m-0 text-xs text-zinc-500")}>{emptyMessage}</p>
      )}
    </section>
  )
}
