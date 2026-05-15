import { Separator } from "@/components/ui/separator"
import { HEADER_BODY_GAP } from "@/components/workspace/shot-metadata/constants"
import { SectionTitle } from "@/components/workspace/shot-metadata/primitives"
import { findShotMatchAssignment } from "@/lib/shot-match-lookup"
import { cn } from "@/lib/utils"
import type { RenderBeat, ShotMatch } from "@/types/vlm"

export function PlanningMetadata({
  shotMatch,
  activeBeat,
}: {
  shotMatch: ShotMatch
  activeBeat: RenderBeat | null
}) {
  const activeAssignment = activeBeat
    ? findShotMatchAssignment(shotMatch, activeBeat.sentenceId)
    : null

  return (
    <>
      {activeAssignment ? (
        <ActiveSentenceSection assignment={activeAssignment} activeBeat={activeBeat} />
      ) : activeBeat ? (
        <section className="min-w-0">
          <SectionTitle>Active sentence @ playhead</SectionTitle>
          <p className={cn(HEADER_BODY_GAP, "m-0 text-xs text-zinc-500")}>
            No shot-match row for {activeBeat.sentenceId}.
          </p>
        </section>
      ) : null}

      <Separator className="bg-zinc-800" />

      <PlanningTraceSection planning={shotMatch._planning} />
    </>
  )
}

function ActiveSentenceSection({
  assignment,
  activeBeat,
}: {
  assignment: NonNullable<ReturnType<typeof findShotMatchAssignment>>
  activeBeat: RenderBeat | null
}) {
  return (
    <section className="min-w-0">
      <SectionTitle>Active sentence @ playhead</SectionTitle>
      <div className={cn(HEADER_BODY_GAP, "flex min-w-0 flex-col gap-2 text-xs")}>
        <p className="m-0 font-mono text-[11px] text-zinc-500">{assignment.sentenceId}</p>
        <p className="m-0 leading-snug text-zinc-300">{assignment.text}</p>
        <ul className="m-0 flex min-w-0 list-none flex-col gap-2 p-0">
          {assignment.shots.map((shot, index) => {
            const isActive =
              activeBeat != null &&
              shot.clipId === activeBeat.clipId &&
              shot.shotId === activeBeat.shotId
            return (
              <li
                key={`${shot.clipId}:${shot.shotId}:${index}`}
                className={cn(
                  "rounded border px-2 py-1.5",
                  isActive ? "border-sky-500/40 bg-sky-500/10" : "border-zinc-800 bg-zinc-950/40",
                )}
              >
                <p className="m-0 font-mono text-[11px] text-zinc-400">
                  {shot.clipId} · {shot.shotId}
                  {shot.beatSpan > 1 ? ` · ${shot.beatSpan} beats` : null}
                </p>
                <p className="m-0 mt-1 leading-snug text-zinc-300">{shot.reasoning}</p>
              </li>
            )
          })}
        </ul>
      </div>
    </section>
  )
}

function PlanningTraceSection({ planning }: { planning?: string }) {
  return (
    <section className="min-w-0">
      <SectionTitle>Planning trace</SectionTitle>
      {planning ? (
        <pre
          className={cn(
            HEADER_BODY_GAP,
            "m-0 max-h-[min(52vh,28rem)] overflow-auto whitespace-pre-wrap break-words rounded border border-zinc-800 bg-zinc-950/50 p-2 font-mono text-[11px] leading-relaxed text-zinc-400",
          )}
        >
          {planning}
        </pre>
      ) : (
        <p className={cn(HEADER_BODY_GAP, "m-0 text-xs text-zinc-500")}>
          No `_planning` field in shot-match.json.
        </p>
      )}
    </section>
  )
}
