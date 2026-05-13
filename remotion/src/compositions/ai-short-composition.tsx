import { useMemo } from 'react';
import {
    AbsoluteFill, Audio, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame,
    useVideoConfig
} from 'remotion';

import { ActiveHookTitle } from '../components/titles';

export type RenderWord = {
  word: string;
  startSec: number;
  endSec: number;
};

export type RenderBeat = {
  beatId: string;
  sentenceId: string;
  clipId: string;
  shotId: string;
  sourcePath: string;
  sourceStartSec: number;
  sourceEndSec: number;
  timelineStartSec: number;
  timelineEndSec: number;
};

export type RenderPlanProps = {
  durationSec: number;
  voiceoverStaticPath: string;
  theme?: {
    hookText?: string;
  };
  beats: RenderBeat[];
  words: RenderWord[];
  /**
   * ``static-file`` keeps existing Remotion Studio behavior.
   * ``api-media`` resolves absolute filesystem media through viewer middleware.
   */
  mediaSourceMode?: 'static-file' | 'api-media';
};

export const WIDTH = 1080;
export const HEIGHT = 1920;
export const FPS = 30;

export const EMPTY_PLAN: RenderPlanProps = {
  durationSec: 35,
  voiceoverStaticPath: '',
  theme: { hookText: '' },
  beats: [],
  words: [],
  mediaSourceMode: 'static-file',
};

export const secondsToFrames = (seconds: number, fps: number) =>
  Math.max(0, Math.round(seconds * fps));

const resolveMediaPath = (pathValue: string, mode: 'static-file' | 'api-media') => {
  if (!pathValue) return '';
  if (mode === 'api-media') {
    if (/^https?:\/\//.test(pathValue)) return pathValue;
    const target = pathValue.startsWith('/')
      ? pathValue
      : `remotion/public/${pathValue.replace(/^\/+/, '')}`;
    return `/api/media?p=${encodeURIComponent(target)}`;
  }
  return staticFile(pathValue);
};

/**
 * Lay out beats on an integer-frame grid without gaps between consecutive beats.
 * Independent rounding of each beat's start/duration causes 1-frame (or more)
 * holes at sentence boundaries → black flashes on a black Composition background.
 */
const layoutBeatFrames = (
  sortedBeats: RenderBeat[],
  fps: number,
): { beat: RenderBeat; from: number; dur: number }[] => {
  let cursorFrame = 0;
  return sortedBeats.map((beat, i) => {
    const endFrame = secondsToFrames(beat.timelineEndSec, fps);
    if (i === 0) {
      cursorFrame = secondsToFrames(beat.timelineStartSec, fps);
    }
    const from = cursorFrame;
    const safeEndFrame = Math.max(endFrame, from + 1);
    const dur = safeEndFrame - from;
    cursorFrame = from + dur;
    return { beat, from, dur };
  });
};

const firstSentenceDurationSec = (
  sortedBeats: RenderBeat[],
  totalDurationSec: number,
): number => {
  const firstSentenceId = sortedBeats[0]?.sentenceId;
  if (!firstSentenceId) return Math.min(5, totalDurationSec);
  let endSec = 0;
  for (const beat of sortedBeats) {
    if (beat.sentenceId !== firstSentenceId) break;
    endSec = Math.max(endSec, beat.timelineEndSec);
  }
  return endSec > 0 ? Math.min(endSec, totalDurationSec) : Math.min(5, totalDurationSec);
};

const WordCaption: React.FC<{ activeWord: RenderWord | null }> = ({ activeWord }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 6], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const text = activeWord?.word ?? '';
  return (
    <div
      style={{
        position: 'absolute',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        width: 'calc(100% - 96px)',
        textAlign: 'center',
        color: '#ffffff',
        fontFamily: 'Inter, Helvetica, Arial, sans-serif',
        fontSize: 42,
        fontWeight: 800,
        letterSpacing: -0.3,
        lineHeight: 1.06,
        backgroundColor: 'transparent',
        WebkitTextStroke: '6px rgba(0,0,0,0.98)',
        paintOrder: 'stroke fill',
        opacity,
        textShadow:
          '0 0 2px rgba(0,0,0,0.98), 0 2px 6px rgba(0,0,0,0.95), 0 6px 18px rgba(0,0,0,0.85)',
      }}
    >
      {text}
    </div>
  );
};

export const AiShortComposition: React.FC<RenderPlanProps> = (plan) => {
  const { fps } = useVideoConfig();
  const frame = useCurrentFrame();
  const t = frame / fps;
  const sourceMode = plan.mediaSourceMode ?? 'static-file';

  const sortedBeats = useMemo(
    () =>
      [...(plan.beats ?? [])].sort(
        (a, b) =>
          a.timelineStartSec - b.timelineStartSec ||
          a.beatId.localeCompare(b.beatId),
      ),
    [plan.beats],
  );
  const beatLayouts = useMemo(
    () => layoutBeatFrames(sortedBeats, fps),
    [sortedBeats, fps],
  );
  const hookDurationSec = useMemo(
    () => Math.min(Math.max(firstSentenceDurationSec(sortedBeats, plan.durationSec), 5), plan.durationSec),
    [sortedBeats, plan.durationSec],
  );
  const hookDurationFrames = secondsToFrames(hookDurationSec, fps);

  const hook = plan.theme?.hookText ?? '';
  const words = plan.words ?? [];

  const activeWord =
    words.find((w) => t >= w.startSec && t < w.endSec) ?? null;

  return (
    <AbsoluteFill style={{ backgroundColor: 'black' }}>
      {beatLayouts.map(({ beat, from, dur }) => {
        const startFrom = secondsToFrames(beat.sourceStartSec, fps);
        const endAt = secondsToFrames(beat.sourceEndSec, fps);
        const sourceDurationSec = beat.sourceEndSec - beat.sourceStartSec;
        const timelineOutSec = dur / fps;
        const rateFromTiming =
          sourceDurationSec > 0 && timelineOutSec > 0
            ? sourceDurationSec / timelineOutSec
            : null;
        const rate =
          rateFromTiming != null &&
            Number.isFinite(rateFromTiming) &&
            rateFromTiming > 0
            ? rateFromTiming
            : 1;

        return (
          <Sequence key={beat.beatId} from={from} durationInFrames={dur}>
            <OffthreadVideo
              src={resolveMediaPath(beat.sourcePath, sourceMode)}
              trimBefore={startFrom}
              // OffthreadVideo has known trim/playback edge cases in some versions.
              // When slowed (rate < 1), omit trimAfter to avoid black tails after trimmed media ends:
              // https://github.com/remotion-dev/remotion/issues/5743
              // https://github.com/remotion-dev/remotion/pull/5752
              // trim semantics reference: https://remotion.dev/docs/offthreadvideo#trimbefore
              trimAfter={rate < 1 ? undefined : endAt}
              muted
              playbackRate={rate}
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
              }}
            />
          </Sequence>
        );
      })}

      {plan.voiceoverStaticPath ? (
        <Audio src={resolveMediaPath(plan.voiceoverStaticPath, sourceMode)} />
      ) : null}

      {hook ? (
        <Sequence from={0} durationInFrames={hookDurationFrames}>
          <ActiveHookTitle text={hook} durationInFrames={hookDurationFrames} />
        </Sequence>
      ) : null}

      <WordCaption activeWord={activeWord} />
    </AbsoluteFill>
  );
};
