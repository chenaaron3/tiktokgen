import { HEADER_BODY_GAP, LABEL_COL } from "@/components/workspace/shot-metadata/constants"
import { MetadataRow, SectionTitle } from "@/components/workspace/shot-metadata/primitives"
import { cn } from "@/lib/utils"
import type { VlmClip } from "@/types/vlm"

export function ClipMetadataSection({
  clip,
  shotCount,
  durationSec,
}: {
  clip: VlmClip | null
  shotCount: number
  durationSec: number
}) {
  return (
    <section className="min-w-0">
      <SectionTitle>Clip metadata</SectionTitle>
      <dl
        className={cn(HEADER_BODY_GAP, "grid min-w-0 gap-x-3 gap-y-1 text-xs")}
        style={{ gridTemplateColumns: `${LABEL_COL} minmax(0, 1fr)` }}
      >
        <MetadataRow label="File" value={clip?.originalFilename ?? clip?.id ?? "—"} />
        <MetadataRow label="Path" value={clip?.sourcePath ?? "—"} mono clamp={2} />
        <MetadataRow label="Captured" value={clip?.capturedAt ?? "—"} />
        <MetadataRow label="Duration" value={durationSec > 0 ? `${durationSec.toFixed(3)} s` : "—"} />
        <MetadataRow label="Shot count" value={String(shotCount)} />
        {clip?.summary ? <MetadataRow label="Summary" value={clip.summary} clamp={3} /> : null}
      </dl>
    </section>
  )
}
