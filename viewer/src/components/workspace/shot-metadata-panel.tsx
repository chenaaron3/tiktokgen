import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"

interface ShotLike {
  vlmTag?: string
  dishName?: string | null
  startSec?: number
  endSec?: number
  keyInstantStartSec?: number
  reasoning?: string
}

interface ClipLike {
  id?: string
  originalFilename?: string
  sourcePath?: string
  capturedAt?: string | null
  summary?: string
}

export function ShotMetadataPanel({
  clip,
  shotCount,
  durationSec,
  activeShot,
  emptyActiveShotMessage,
}: {
  clip: ClipLike | null
  shotCount: number
  durationSec: number
  activeShot: ShotLike | null
  emptyActiveShotMessage: string
}) {
  return (
    <ScrollArea className="min-h-0 flex-1 rounded-lg border border-zinc-700 bg-zinc-900/50">
      <div className="space-y-3 p-4 text-sm text-zinc-200">
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Clip metadata</h2>
          <dl className="mt-2 grid grid-cols-[112px_minmax(0,1fr)] gap-x-2 gap-y-1 text-xs">
            <MetadataRow label="File" value={clip?.originalFilename ?? clip?.id ?? "—"} />
            <MetadataRow label="Path" value={clip?.sourcePath ?? "—"} mono />
            <MetadataRow label="Captured" value={clip?.capturedAt ?? "—"} />
            <MetadataRow label="Duration" value={durationSec > 0 ? `${durationSec.toFixed(3)} s` : "—"} />
            <MetadataRow label="Shot count" value={String(shotCount)} />
            {clip?.summary ? <MetadataRow label="Summary" value={clip.summary} mono /> : null}
          </dl>
        </div>

        <Separator className="bg-zinc-800" />

        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Active shot @ playhead</h2>
          {activeShot ? (
            <div className="mt-2 space-y-2 text-xs">
              <MetadataRow label="Tag" value={activeShot.vlmTag ?? "—"} />
              <MetadataRow label="Dish" value={activeShot.dishName ?? "—"} />
              <MetadataRow label="Range" value={`${activeShot.startSec ?? "—"} – ${activeShot.endSec ?? "—"} s`} />
              <MetadataRow label="Key moment" value={`${activeShot.keyInstantStartSec ?? "—"} s`} />
              <p className="leading-relaxed text-zinc-400">
                <span className="font-medium text-zinc-200">Reasoning:</span> {activeShot.reasoning ?? "—"}
              </p>
            </div>
          ) : (
            <p className="mt-2 text-xs text-zinc-500">{emptyActiveShotMessage}</p>
          )}
        </div>
      </div>
    </ScrollArea>
  )
}

function MetadataRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <>
      <dt className="text-zinc-500">{label}</dt>
      <dd className={mono ? "break-all font-mono text-[11px] leading-snug" : undefined}>{value}</dd>
    </>
  )
}
