import { HEADER_BODY_GAP } from "@/components/workspace/shot-metadata/constants"
import {
  ConfidenceBadge,
  FactSeparator,
  ProseRow,
} from "@/components/workspace/shot-metadata/primitives"
import { formatVerifiedBy } from "@/lib/shot-label-meta"
import { cn } from "@/lib/utils"
import type { IdentifiedShot } from "@/types/vlm"

export function ActiveShotMetadata({
  shot,
  matchReasoning,
}: {
  shot: IdentifiedShot
  matchReasoning?: string | null
}) {
  const range = `${shot.startSec ?? "—"} – ${shot.endSec ?? "—"} s`
  const keyMoment = shot.keyInstantStartSec != null ? `key @ ${shot.keyInstantStartSec} s` : "key —"
  const dish = shot.dishName ?? "—"

  return (
    <div className={cn(HEADER_BODY_GAP, "flex min-w-0 flex-col gap-2 text-xs")}>
      <div className="flex min-w-0 flex-col gap-0.5">
        <div className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
          <span className="font-medium text-zinc-100">{shot.vlmTag ?? "—"}</span>
          <ConfidenceBadge confidence={shot.labelConfidence} />
          <span className="select-none text-zinc-600" aria-hidden>
            ·
          </span>
          <span className="text-zinc-400">{formatVerifiedBy(shot.verifiedBy)}</span>
        </div>
        <div className="min-w-0 leading-snug text-zinc-500">
          {range}
          <FactSeparator />
          {keyMoment}
          <FactSeparator />
          <span>
            dish <span className="text-zinc-400">{dish}</span>
          </span>
        </div>
      </div>

      <div className="flex min-w-0 flex-col gap-2 border-t border-zinc-800/90 pt-2">
        {shot.semanticContext ? <ProseRow label="Semantic" text={shot.semanticContext} /> : null}
        <ProseRow label="VLM" text={shot.reasoning ?? "—"} />
        {matchReasoning ? <ProseRow label="Match" text={matchReasoning} highlight /> : null}
      </div>
    </div>
  )
}
