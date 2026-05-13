import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
    PREVIEW_FPS, PREVIEW_HEIGHT, PREVIEW_WIDTH, RenderPlanPreviewComposition
} from '@/components/workspace/preview-composition';
import { ShotMetadataPanel } from '@/components/workspace/shot-metadata-panel';
import { ShotTimeline } from '@/components/workspace/shot-timeline';
import { WorkspaceLayout } from '@/components/workspace/workspace-layout';
import { Player } from '@remotion/player';

import type { TimelineMoment, TimelineSegment } from '@/components/workspace/shot-timeline';
import type { PlayerRef } from '@remotion/player';

import type { IdentifiedShot, RenderBeat, RenderPlan, VlmAnalysis, VlmClip } from "@/types/vlm"

function clipDurationSec(clip: VlmClip): number {
  const d = clip.durationSec ?? clip.media?.durationSec
  return typeof d === "number" && Number.isFinite(d) && d > 0 ? d : 0
}

function activeBeatForTime(beats: RenderBeat[], t: number): RenderBeat | null {
  for (const beat of beats) {
    if (t >= beat.timelineStartSec && t <= beat.timelineEndSec) return beat
  }
  return null
}

function shotKey(clipId: string | undefined, shotId: string | undefined): string {
  return `${clipId ?? ""}::${shotId ?? ""}`
}

export function PreviewWorkspace({ analysis, renderPlan }: { analysis: VlmAnalysis | null; renderPlan: RenderPlan | null }) {
  const playerRef = useRef<PlayerRef>(null)
  const [playheadSec, setPlayheadSec] = useState(0)
  const safeClips = useMemo(() => analysis?.clips ?? [], [analysis?.clips])
  const safeRenderPlan = useMemo(
    () => renderPlan ?? { durationSec: 0, voiceoverStaticPath: "", beats: [], words: [] },
    [renderPlan],
  )
  const playerInputProps = useMemo(() => ({ plan: safeRenderPlan }), [safeRenderPlan])

  const clipsById = useMemo(() => {
    const m = new Map<string, VlmClip>()
    for (const clip of safeClips) {
      if (clip.id) m.set(clip.id, clip)
    }
    return m
  }, [safeClips])

  const shotsByRef = useMemo(() => {
    const m = new Map<string, IdentifiedShot>()
    for (const clip of safeClips) {
      for (const shot of clip.identifiedShots ?? []) {
        m.set(shotKey(clip.id, shot.shotId), shot)
      }
    }
    return m
  }, [safeClips])

  const beatsSorted = useMemo(
    () =>
      [...(safeRenderPlan.beats ?? [])].sort(
        (a, b) => a.timelineStartSec - b.timelineStartSec || a.beatId.localeCompare(b.beatId),
      ),
    [safeRenderPlan.beats],
  )

  const timelineSegments: TimelineSegment[] = useMemo(
    () =>
      beatsSorted.map((beat) => {
        const shot = shotsByRef.get(shotKey(beat.clipId, beat.shotId))
        const label = shot?.vlmTag ?? beat.shotId
        return {
          id: beat.beatId,
          startSec: beat.timelineStartSec,
          endSec: beat.timelineEndSec,
          label,
          title: `${beat.clipId} • ${beat.shotId}`,
        }
      }),
    [beatsSorted, shotsByRef],
  )

  const keyMoments: TimelineMoment[] = useMemo(
    () =>
      beatsSorted.flatMap((beat) => {
        const shot = shotsByRef.get(shotKey(beat.clipId, beat.shotId))
        if (!shot) return []
        const sourceSpan = beat.sourceEndSec - beat.sourceStartSec
        if (!(sourceSpan > 0)) return []
        const moment = typeof shot.keyInstantStartSec === "number" ? shot.keyInstantStartSec : shot.startSec
        if (typeof moment !== "number") return []
        const frac = (moment - beat.sourceStartSec) / sourceSpan
        const clamped = Math.min(1, Math.max(0, frac))
        const timelineMoment = beat.timelineStartSec + clamped * (beat.timelineEndSec - beat.timelineStartSec)
        return [
          {
            id: `moment-${beat.beatId}`,
            sec: timelineMoment,
            title: `${shot.vlmTag ?? beat.shotId} • key moment`,
          },
        ]
      }),
    [beatsSorted, shotsByRef],
  )

  const activeBeat = activeBeatForTime(beatsSorted, playheadSec)
  const activeClip = activeBeat ? clipsById.get(activeBeat.clipId) ?? null : null
  const activeShot = activeBeat ? shotsByRef.get(shotKey(activeBeat.clipId, activeBeat.shotId)) ?? null : null

  const seekTo = useCallback((nextSec: number) => {
    const frame = Math.round(nextSec * PREVIEW_FPS)
    playerRef.current?.seekTo(frame)
    setPlayheadSec(nextSec)
  }, [])

  useEffect(() => {
    const player = playerRef.current
    if (!player) return
    const onFrameUpdate = (event: { detail: { frame: number } }) => {
      setPlayheadSec(event.detail.frame / PREVIEW_FPS)
    }
    player.addEventListener("frameupdate", onFrameUpdate)
    return () => {
      player.removeEventListener("frameupdate", onFrameUpdate)
    }
  }, [])

  if (!analysis || !renderPlan) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center px-8 text-center text-sm text-zinc-500">
        Preview is unavailable for this run.
      </div>
    )
  }

  return (
    <WorkspaceLayout
      player={
        <div className="flex min-h-0 flex-1 items-center justify-center overflow-hidden rounded-lg border border-zinc-700 bg-black">
          <Player
            ref={playerRef}
            component={RenderPlanPreviewComposition}
            inputProps={playerInputProps}
            durationInFrames={Math.max(1, Math.round(safeRenderPlan.durationSec * PREVIEW_FPS))}
            compositionWidth={PREVIEW_WIDTH}
            compositionHeight={PREVIEW_HEIGHT}
            fps={PREVIEW_FPS}
            controls
            loop={false}
            acknowledgeRemotionLicense
            style={{ width: "100%", height: "100%", maxHeight: "100%" }}
          />
        </div>
      }
      metadata={
        <ShotMetadataPanel
          clip={activeClip}
          shotCount={activeClip?.identifiedShots?.length ?? 0}
          durationSec={activeClip ? clipDurationSec(activeClip) : 0}
          activeShot={activeShot}
          emptyActiveShotMessage="No stitched clip spans the current playback time."
        />
      }
      timeline={
        <ShotTimeline
          title="Stitched timeline"
          durationSec={safeRenderPlan.durationSec}
          currentTimeSec={playheadSec}
          segments={timelineSegments}
          keyMoments={keyMoments}
          onSeek={seekTo}
        />
      }
    />
  )
}
