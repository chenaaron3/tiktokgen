import { useState } from "react"

import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { ActiveShotSection } from "@/components/workspace/shot-metadata/active-shot-section"
import { ClipMetadataSection } from "@/components/workspace/shot-metadata/clip-metadata-section"
import { PANEL_PAD, SECTION_GAP } from "@/components/workspace/shot-metadata/constants"
import {
  MetadataModeToggle,
  type ShotMetadataPanelMode,
} from "@/components/workspace/shot-metadata/metadata-mode-toggle"
import { PlanningMetadata } from "@/components/workspace/shot-metadata/planning-metadata"
import { cn } from "@/lib/utils"
import type { IdentifiedShot, RenderBeat, ShotMatch, VlmClip } from "@/types/vlm"

export type { ShotMetadataPanelMode }

export function ShotMetadataPanel({
  clip,
  shotCount,
  durationSec,
  activeShot,
  emptyActiveShotMessage,
  shotMatch,
  activeBeat,
  matchReasoning,
}: {
  clip: VlmClip | null
  shotCount: number
  durationSec: number
  activeShot: IdentifiedShot | null
  emptyActiveShotMessage: string
  shotMatch?: ShotMatch | null
  activeBeat?: RenderBeat | null
  matchReasoning?: string | null
}) {
  const planningAvailable = Boolean(shotMatch)
  const [mode, setMode] = useState<ShotMetadataPanelMode>("shot")

  return (
    <ScrollArea className="min-h-0 flex-1 rounded-lg border border-zinc-700 bg-zinc-900/50">
      <div className={cn("flex w-full min-w-0 flex-col text-sm text-zinc-200", PANEL_PAD, SECTION_GAP)}>
        {planningAvailable ? (
          <MetadataModeToggle mode={mode} onModeChange={setMode} />
        ) : null}

        {mode === "planning" && shotMatch ? (
          <PlanningMetadata shotMatch={shotMatch} activeBeat={activeBeat ?? null} />
        ) : (
          <>
            <ClipMetadataSection clip={clip} shotCount={shotCount} durationSec={durationSec} />
            <Separator className="bg-zinc-800" />
            <ActiveShotSection
              activeShot={activeShot}
              emptyMessage={emptyActiveShotMessage}
              matchReasoning={matchReasoning}
            />
          </>
        )}
      </div>
    </ScrollArea>
  )
}
