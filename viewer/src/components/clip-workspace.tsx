import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import { ShotMetadataPanel } from "@/components/workspace/shot-metadata-panel"
import { ShotTimeline, type TimelineMoment, type TimelineSegment } from "@/components/workspace/shot-timeline"
import { WorkspaceLayout } from "@/components/workspace/workspace-layout"
import type { IdentifiedShot, VlmClip } from "@/types/vlm"

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

export function ClipWorkspace({ clip }: { clip: VlmClip | null }) {
  const videoRef = useRef<HTMLVideoElement>(null)
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

  const activeShot =
    timelineDuration > 0 && shots.length > 0 ? activeShotForTime(shots, mediaTime) : null

  const seekTo = useCallback((target: number) => {
    const v = videoRef.current
    if (!v) return
    v.currentTime = target
    setMediaTime(target)
  }, [])

  if (!clip) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center px-8 text-center text-sm text-zinc-500">
        Select a run and clip from the sidebar.
      </div>
    )
  }

  const url = mediaUrl(clip.sourcePath)

  const timelineSegments: TimelineSegment[] = shots.map((shot, idx) => ({
    id: `shot-${idx}-${shot.shotId ?? "unknown"}`,
    startSec: shot.startSec ?? 0,
    endSec: shot.endSec ?? 0,
    label: shot.vlmTag ?? "?",
    title: shot.vlmTag ?? "?",
  }))

  const keyMoments: TimelineMoment[] = shots.map((shot, idx) => {
    const st = shot.startSec ?? 0
    const en = shot.endSec ?? st
    const fallbackMoment = st + (en - st) / 2
    const rawMoment = typeof shot.keyInstantStartSec === "number" ? shot.keyInstantStartSec : fallbackMoment
    const keyMoment = Math.min(en, Math.max(st, rawMoment))
    return {
      id: `key-${idx}-${shot.shotId ?? "unknown"}`,
      sec: keyMoment,
      title: `${shot.vlmTag ?? "shot"} • key moment ${keyMoment.toFixed(2)}s`,
    }
  })

  return (
    <WorkspaceLayout
      player={
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
      }
      metadata={
        <ShotMetadataPanel
          clip={clip}
          shotCount={shots.length}
          durationSec={timelineDuration}
          activeShot={activeShot}
          emptyActiveShotMessage="No annotated shot spans the current playback time."
        />
      }
      timeline={
        <ShotTimeline
          title="Timeline"
          durationSec={timelineDuration}
          currentTimeSec={mediaTime}
          segments={timelineSegments}
          keyMoments={keyMoments}
          onSeek={seekTo}
        />
      }
    />
  )
}

function Placeholder({ label }: { label: string }) {
  return (
    <div className="flex max-h-full min-h-[120px] w-full max-w-full flex-1 items-center justify-center px-4 text-center text-sm text-zinc-500">
      {label}
    </div>
  )
}
