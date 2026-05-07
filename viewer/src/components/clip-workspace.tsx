import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react"

import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { shotLabelColor } from "@/lib/tag-color"
import { cn } from "@/lib/utils"
import type { IdentifiedShot, VlmClip } from "@/types/vlm"

/** Fixed height of the scrub strip (label row is outside this). */
const TIMELINE_TRACK_PX = 72

function clipDurationSec(clip: VlmClip): number {
  const d = clip.durationSec ?? clip.media?.durationSec
  return typeof d === "number" && Number.isFinite(d) && d > 0 ? d : 0
}

function normalizeShots(clip: VlmClip): IdentifiedShot[] {
  const raw = clip.identifiedShots
  if (!Array.isArray(raw)) return []
  return raw.filter((s): s is IdentifiedShot => {
    const st = typeof s?.startSec === "number"
    const en = typeof s?.endSec === "number"
    return Boolean(st && en && (s!.endSec as number) > (s!.startSec as number))
  })
}

function mediaUrl(sourcePath: string | undefined): string | null {
  if (!sourcePath) return null
  return `/api/media?p=${encodeURIComponent(sourcePath)}`
}

function activeShotForTime(shots: IdentifiedShot[], t: number): IdentifiedShot | null {
  for (const s of shots) {
    const start = s.startSec ?? 0
    const end = s.endSec ?? 0
    if (t >= start && t <= end) return s
  }
  return null
}

function spanCenter(start: number, end: number): number {
  return (end - start) / 2
}

export function ClipWorkspace({ clip }: { clip: VlmClip | null }) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const trackRef = useRef<HTMLDivElement>(null)
  const [mediaTime, setMediaTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [decodeError, setDecodeError] = useState<string | null>(null)

  const shots = useMemo(() => (clip ? normalizeShots(clip) : []), [clip])
  const nominalDuration = clip ? clipDurationSec(clip) : 0

  useEffect(() => {
    const v = videoRef.current
    if (!v) return
    const onTime = () => setMediaTime(v.currentTime)
    const onDur = () => setDuration(Number.isFinite(v.duration) ? v.duration : 0)
    const onEnded = () => setMediaTime(v.currentTime)
    v.addEventListener("timeupdate", onTime)
    v.addEventListener("durationchange", onDur)
    v.addEventListener("loadedmetadata", onDur)
    v.addEventListener("ended", onEnded)
    return () => {
      v.removeEventListener("timeupdate", onTime)
      v.removeEventListener("durationchange", onDur)
      v.removeEventListener("loadedmetadata", onDur)
      v.removeEventListener("ended", onEnded)
    }
  }, [clip?.sourcePath])

  const timelineDuration = nominalDuration > 0 ? nominalDuration : duration > 0 ? duration : 0

  const playheadFrac = timelineDuration > 0 ? Math.min(1, Math.max(0, mediaTime / timelineDuration)) : 0

  const activeShot =
    timelineDuration > 0 && shots.length > 0 ? activeShotForTime(shots, mediaTime) : null

  const scrub = useCallback(
    (clientX: number, trackEl: HTMLDivElement) => {
      if (timelineDuration <= 0) return
      const rect = trackEl.getBoundingClientRect()
      const x = Math.min(Math.max(clientX - rect.left, 0), rect.width)
      const frac = rect.width > 0 ? x / rect.width : 0
      const target = frac * timelineDuration
      const v = videoRef.current
      if (v) {
        v.currentTime = target
        setMediaTime(target)
      }
    },
    [timelineDuration],
  )

  const handleTrackPointerDown = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      if (timelineDuration <= 0) return
      if (e.pointerType === "mouse" && e.button !== 0) return
      e.preventDefault()
      e.currentTarget.setPointerCapture(e.pointerId)
      scrub(e.clientX, e.currentTarget)
    },
    [timelineDuration, scrub],
  )

  const handleTrackPointerMove = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      if (timelineDuration <= 0) return
      if (!e.currentTarget.hasPointerCapture(e.pointerId)) return
      scrub(e.clientX, e.currentTarget)
    },
    [timelineDuration, scrub],
  )

  const handleTrackPointerUp = useCallback((e: ReactPointerEvent<HTMLDivElement>) => {
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId)
    }
  }, [])

  if (!clip) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center px-8 text-center text-sm text-zinc-500">
        Select a run and clip from the sidebar.
      </div>
    )
  }

  const url = mediaUrl(clip.sourcePath)

  const metadataPanel = (
    <ScrollArea className="min-h-0 flex-1 rounded-lg border border-zinc-700 bg-zinc-900/50">
      <div className="space-y-3 p-4 text-sm text-zinc-200">
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Clip metadata</h2>
          <dl className="mt-2 grid grid-cols-[112px_minmax(0,1fr)] gap-x-2 gap-y-1 text-xs">
            <MetadataRow label="File" value={clip.originalFilename ?? clip.id ?? "—"} />
            <MetadataRow label="Path" value={clip.sourcePath ?? "—"} mono />
            <MetadataRow label="Captured" value={clip.capturedAt ?? "—"} />
            <MetadataRow
              label="Duration"
              value={timelineDuration > 0 ? `${timelineDuration.toFixed(3)} s` : "—"}
            />
            <MetadataRow label="Shot count" value={String(shots.length)} />
            {clip.summary ? <MetadataRow label="Summary" value={clip.summary} mono /> : null}
          </dl>
        </div>

        <Separator className="bg-zinc-800" />

        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Active shot @ playhead</h2>
          {activeShot ? (
            <div className="mt-2 space-y-2 text-xs">
              <MetadataRow label="Tag" value={activeShot.vlmTag ?? "—"} />
              <MetadataRow
                label="Confidence"
                value={
                  typeof activeShot.confidenceScore === "number" ? activeShot.confidenceScore.toFixed(3) : "—"
                }
              />
              <MetadataRow label="Range" value={`${activeShot.startSec ?? "—"} – ${activeShot.endSec ?? "—"} s`} />
              <MetadataRow label="Key instant" value={`${activeShot.keyInstantSec ?? "—"} s`} />
              <p className="leading-relaxed text-zinc-400">
                <span className="font-medium text-zinc-200">Reasoning:</span> {activeShot.reasoning ?? "—"}
              </p>
            </div>
          ) : (
            <p className="mt-2 text-xs text-zinc-500">No annotated shot spans the current playback time.</p>
          )}
        </div>
      </div>
    </ScrollArea>
  )

  const timelineBlock = (
    <div className={cn(timelineDuration <= 0 && "opacity-70")}>
      {timelineDuration <= 0 ? (
        <div
          className="flex w-full items-center justify-center rounded-md bg-zinc-900/90 text-xs text-zinc-500 ring-1 ring-zinc-700"
          style={{ height: TIMELINE_TRACK_PX }}
        >
          No duration data • empty timeline
        </div>
      ) : (
        <div
          ref={trackRef}
          className="relative isolate w-full cursor-grab touch-none select-none rounded-md bg-zinc-950 px-px ring-2 ring-zinc-600 outline-none active:cursor-grabbing focus-visible:ring-zinc-400"
          style={{ height: TIMELINE_TRACK_PX }}
          role="slider"
          aria-label="Scrub clip timeline"
          aria-valuemin={0}
          aria-valuemax={timelineDuration}
          aria-valuenow={Math.min(mediaTime, timelineDuration)}
          tabIndex={0}
          onPointerDown={handleTrackPointerDown}
          onPointerMove={handleTrackPointerMove}
          onPointerUp={handleTrackPointerUp}
          onPointerCancel={handleTrackPointerUp}
          onLostPointerCapture={handleTrackPointerUp}
          onKeyDown={(e) => {
            const v = videoRef.current
            if (!v) return
            const step = timelineDuration / 50
            if (e.key === "ArrowLeft") {
              e.preventDefault()
              const next = Math.max(0, v.currentTime - step)
              v.currentTime = next
              setMediaTime(next)
            }
            if (e.key === "ArrowRight") {
              e.preventDefault()
              const next = Math.min(timelineDuration, v.currentTime + step)
              v.currentTime = next
              setMediaTime(next)
            }
          }}
        >
          {shots.map((s, idx) => {
            const tag = s.vlmTag ?? "?"
            const st = Math.max(0, s.startSec ?? 0)
            const en = Math.min(timelineDuration, s.endSec ?? 0)
            const span = Math.max(en - st, 0)
            const leftPct = timelineDuration > 0 ? (st / timelineDuration) * 100 : 0
            const widthPct = timelineDuration > 0 ? (span / timelineDuration) * 100 : 0
            const palette = shotLabelColor(tag)
            return (
              <div
                key={`shot-${idx}-${tag}-${st}-${en}`}
                className="pointer-events-none absolute inset-y-1 z-[15]"
                style={{
                  left: `${leftPct}%`,
                  width: `${widthPct}%`,
                }}
              >
                <div
                  aria-hidden
                  className="absolute inset-0 rounded-[3px] border border-black/50 shadow-inner"
                  style={{ backgroundColor: palette.bg }}
                />
                <div
                  aria-hidden
                  className="absolute top-px bottom-px left-0 z-[17] w-1 rounded-l-[2px] bg-zinc-100 shadow-[2px_0_3px_rgba(0,0,0,.45)] ring-1 ring-zinc-900/60"
                />
                <div
                  aria-hidden
                  className="absolute top-px bottom-px right-0 z-[17] w-1 rounded-r-[2px] bg-zinc-100 shadow-[-2px_0_3px_rgba(0,0,0,.45)] ring-1 ring-zinc-900/60"
                />
                <div className="absolute inset-0 z-[18] flex items-center justify-center px-4 py-1">
                  <span
                    className="max-w-full text-center text-[10px] font-semibold leading-snug line-clamp-2 hyphens-none"
                    style={{ color: palette.fg }}
                    title={tag}
                  >
                    {tag}
                  </span>
                </div>
              </div>
            )
          })}

          {shots.map((s, idx) => {
            const tag = s.vlmTag ?? "?"
            const st = Math.max(0, s.startSec ?? 0)
            const en = Math.min(timelineDuration, s.endSec ?? 0)
            const fallbackKey = st + spanCenter(st, en)
            let keyInstant = typeof s.keyInstantSec === "number" ? s.keyInstantSec : fallbackKey
            keyInstant = Math.min(en, Math.max(st, keyInstant))
            const keyGlobalPct = timelineDuration > 0 ? (keyInstant / timelineDuration) * 100 : 0
            return (
              <div
                key={`key-${idx}-${tag}`}
                title={`${tag} • key ${keyInstant.toFixed(2)}s`}
                className="pointer-events-none absolute top-0 bottom-0 z-[32] -translate-x-1/2"
                style={{ left: `${keyGlobalPct}%` }}
              >
                <div
                  aria-hidden
                  className="absolute top-0 bottom-0 left-1/2 w-px -translate-x-1/2 bg-amber-300/95 shadow-[1px_0_0_rgb(24_24_27_/_35%)]"
                />
                <div
                  aria-hidden
                  className="absolute left-1/2 top-1/2 z-[1] size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-zinc-950 bg-amber-300 shadow-sm"
                />
              </div>
            )
          })}

          <div
            aria-hidden
            className="pointer-events-none absolute top-0 bottom-0 z-[45] w-[3px] -translate-x-1/2 rounded-full bg-amber-400 shadow-[0_0_10px_rgba(251,191,36,.7)] ring-2 ring-zinc-950"
            style={{ left: `${playheadFrac * 100}%` }}
          />
        </div>
      )}
    </div>
  )

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Video (50%) + metadata (50%) — share all space above the timeline */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-row">
        <div className="flex min-h-0 min-w-0 flex-1 basis-0 flex-col border-r border-zinc-800 p-3">
          <div className="flex min-h-0 flex-1 items-center justify-center overflow-hidden rounded-lg border border-zinc-700 bg-black">
            {!url ? (
              <Placeholder label="Missing source path" />
            ) : decodeError ? (
              <Placeholder label={decodeError} />
            ) : (
              <video
                key={clip.sourcePath ?? url}
                ref={videoRef}
                src={url}
                className="max-h-full max-w-full object-contain"
                controls
                playsInline
                onError={() => setDecodeError("Video unavailable or unsupported in this browser.")}
              />
            )}
          </div>
        </div>

        <div className="flex min-h-0 min-w-0 flex-1 basis-0 flex-col p-3 pl-4">{metadataPanel}</div>
      </div>

      {/* Full-width timeline, fixed track height */}
      <div className="shrink-0 border-t border-zinc-800 bg-zinc-950/40 px-4 py-2">
        <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-zinc-500">Timeline</p>
        {timelineBlock}
      </div>
    </div>
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

function Placeholder({ label }: { label: string }) {
  return (
    <div className="flex max-h-full min-h-[120px] w-full max-w-full flex-1 items-center justify-center px-4 text-center text-sm text-zinc-500">
      {label}
    </div>
  )
}
