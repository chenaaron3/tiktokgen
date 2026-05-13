import { useCallback, type PointerEvent as ReactPointerEvent } from "react"

import { shotLabelColor } from "@/lib/tag-color"
import { cn } from "@/lib/utils"

/** Fixed height of the scrub strip (label row is outside this). */
const TIMELINE_TRACK_PX = 72

export interface TimelineSegment {
  id: string
  startSec: number
  endSec: number
  label: string
  title?: string
}

export interface TimelineMoment {
  id: string
  sec: number
  title?: string
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function gapSegments(segments: TimelineSegment[], durationSec: number): Array<{ startSec: number; endSec: number }> {
  if (durationSec <= 0) return []
  const sorted = [...segments]
    .map((s) => ({
      startSec: clamp(s.startSec, 0, durationSec),
      endSec: clamp(s.endSec, 0, durationSec),
    }))
    .filter((s) => s.endSec > s.startSec)
    .sort((a, b) => a.startSec - b.startSec)

  const gaps: Array<{ startSec: number; endSec: number }> = []
  let cursor = 0
  for (const segment of sorted) {
    if (segment.startSec > cursor) {
      gaps.push({ startSec: cursor, endSec: segment.startSec })
    }
    cursor = Math.max(cursor, segment.endSec)
  }
  if (cursor < durationSec) {
    gaps.push({ startSec: cursor, endSec: durationSec })
  }
  return gaps
}

export function ShotTimeline({
  title,
  durationSec,
  currentTimeSec,
  segments,
  keyMoments,
  onSeek,
}: {
  title: string
  durationSec: number
  currentTimeSec: number
  segments: TimelineSegment[]
  keyMoments: TimelineMoment[]
  onSeek: (nextSec: number) => void
}) {
  const seekFromClientX = useCallback(
    (clientX: number, trackEl: HTMLDivElement) => {
      if (durationSec <= 0) return
      const rect = trackEl.getBoundingClientRect()
      const x = clamp(clientX - rect.left, 0, rect.width)
      const frac = rect.width > 0 ? x / rect.width : 0
      onSeek(frac * durationSec)
    },
    [durationSec, onSeek],
  )

  const handleTrackPointerDown = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      if (durationSec <= 0) return
      if (e.pointerType === "mouse" && e.button !== 0) return
      e.preventDefault()
      e.currentTarget.setPointerCapture(e.pointerId)
      seekFromClientX(e.clientX, e.currentTarget)
    },
    [durationSec, seekFromClientX],
  )

  const handleTrackPointerMove = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      if (durationSec <= 0) return
      if (!e.currentTarget.hasPointerCapture(e.pointerId)) return
      seekFromClientX(e.clientX, e.currentTarget)
    },
    [durationSec, seekFromClientX],
  )

  const handleTrackPointerUp = useCallback((e: ReactPointerEvent<HTMLDivElement>) => {
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId)
    }
  }, [])

  const playheadFrac = durationSec > 0 ? clamp(currentTimeSec / durationSec, 0, 1) : 0
  const gaps = gapSegments(segments, durationSec)

  return (
    <div className="shrink-0 border-t border-zinc-800 bg-zinc-950/40 px-4 py-2">
      <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-zinc-500">{title}</p>
      <div className={cn(durationSec <= 0 && "opacity-70")}>
        {durationSec <= 0 ? (
          <div
            className="flex w-full items-center justify-center rounded-md bg-zinc-900/90 text-xs text-zinc-500 ring-1 ring-zinc-700"
            style={{ height: TIMELINE_TRACK_PX }}
          >
            No duration data • empty timeline
          </div>
        ) : (
          <div
            className="relative isolate w-full cursor-grab touch-none select-none rounded-md bg-zinc-950 px-px ring-2 ring-zinc-600 outline-none active:cursor-grabbing focus-visible:ring-zinc-400"
            style={{ height: TIMELINE_TRACK_PX }}
            role="slider"
            aria-label={`Scrub ${title.toLowerCase()}`}
            aria-valuemin={0}
            aria-valuemax={durationSec}
            aria-valuenow={Math.min(currentTimeSec, durationSec)}
            tabIndex={0}
            onPointerDown={handleTrackPointerDown}
            onPointerMove={handleTrackPointerMove}
            onPointerUp={handleTrackPointerUp}
            onPointerCancel={handleTrackPointerUp}
            onLostPointerCapture={handleTrackPointerUp}
            onKeyDown={(e) => {
              const step = durationSec / 50
              if (e.key === "ArrowLeft") {
                e.preventDefault()
                onSeek(clamp(currentTimeSec - step, 0, durationSec))
              }
              if (e.key === "ArrowRight") {
                e.preventDefault()
                onSeek(clamp(currentTimeSec + step, 0, durationSec))
              }
            }}
          >
            {gaps.map((gap, idx) => {
              const leftPct = (gap.startSec / durationSec) * 100
              const widthPct = ((gap.endSec - gap.startSec) / durationSec) * 100
              return (
                <div
                  key={`gap-${idx}`}
                  aria-hidden
                  className="pointer-events-none absolute inset-y-1 z-[6] rounded-[3px] border border-zinc-700/80 bg-zinc-800/25"
                  style={{
                    left: `${leftPct}%`,
                    width: `${widthPct}%`,
                    backgroundImage:
                      "repeating-linear-gradient(135deg, rgba(113,113,122,0.22) 0px, rgba(113,113,122,0.22) 6px, rgba(24,24,27,0.25) 6px, rgba(24,24,27,0.25) 12px)",
                  }}
                />
              )
            })}

            {segments.map((segment) => {
              const st = clamp(segment.startSec, 0, durationSec)
              const en = clamp(segment.endSec, 0, durationSec)
              const span = Math.max(en - st, 0)
              const leftPct = durationSec > 0 ? (st / durationSec) * 100 : 0
              const widthPct = durationSec > 0 ? (span / durationSec) * 100 : 0
              const palette = shotLabelColor(segment.label || "?")
              return (
                <div
                  key={segment.id}
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
                    title={segment.title ?? segment.label}
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
                      title={segment.title ?? segment.label}
                    >
                      {segment.label}
                    </span>
                  </div>
                </div>
              )
            })}

            {keyMoments.map((moment) => {
              const keyPct = durationSec > 0 ? (clamp(moment.sec, 0, durationSec) / durationSec) * 100 : 0
              return (
                <div key={moment.id} className="pointer-events-none absolute inset-0 z-[32]">
                  <div
                    aria-hidden
                    title={moment.title}
                    className="absolute top-0 bottom-0 -translate-x-1/2"
                    style={{ left: `${keyPct}%` }}
                  >
                    <div className="absolute top-0 bottom-0 left-1/2 w-px -translate-x-1/2 bg-amber-300/95 shadow-[1px_0_0_rgb(24_24_27_/_35%)]" />
                    <div className="absolute left-1/2 top-1/2 z-[1] size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-zinc-950 bg-amber-300 shadow-sm" />
                  </div>
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
    </div>
  )
}
