import {
  AbsoluteFill,
  Audio,
  Composition,
  OffthreadVideo,
  Sequence,
  interpolate,
  registerRoot,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { useMemo } from 'react';

export type RenderWord = {
  word: string;
  startSec: number;
  endSec: number;
};

export type RenderBeat = {
  beatId: string;
  sentenceId: string;
  clipId: string;
  momentId: string;
  sourcePath: string;
  sourceStartSec: number;
  sourceEndSec: number;
  timelineStartSec: number;
  timelineEndSec: number;
  playbackRate: number;
};

export type RenderPlanProps = {
  durationSec: number;
  voiceoverStaticPath: string;
  theme?: {
    hookText?: string;
  };
  beats: RenderBeat[];
  words: RenderWord[];
};

const WIDTH = 1080;
const HEIGHT = 1920;
const FPS = 30;

const EMPTY_PLAN: RenderPlanProps = {
  durationSec: 35,
  voiceoverStaticPath: '',
  theme: { hookText: '' },
  beats: [],
  words: [],
};

const fileUrl = (sourcePath: string) => {
  if (sourcePath.startsWith('static:')) {
    return staticFile(sourcePath.slice('static:'.length));
  }
  if (sourcePath.startsWith('http://') || sourcePath.startsWith('https://')) {
    return sourcePath;
  }
  if (sourcePath.startsWith('file://')) {
    return encodeURI(sourcePath);
  }
  return encodeURI(`file://${sourcePath}`);
};

const secondsToFrames = (seconds: number, fps: number) =>
  Math.max(0, Math.round(seconds * fps));

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
        bottom: 120,
        left: 48,
        right: 48,
        textAlign: 'center',
        color: 'rgba(255,255,255,0.92)',
        fontFamily: 'Inter, Helvetica, Arial, sans-serif',
        fontSize: 42,
        fontWeight: 500,
        letterSpacing: 0.2,
        opacity,
        textShadow: '0 4px 20px rgba(0,0,0,0.75)',
      }}
    >
      {text}
    </div>
  );
};

const AiShortComposition: React.FC<RenderPlanProps> = (plan) => {
  const { fps } = useVideoConfig();
  const frame = useCurrentFrame();
  const t = frame / fps;

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
            : typeof beat.playbackRate === 'number' && beat.playbackRate > 0
              ? beat.playbackRate
              : 1;

        return (
          <Sequence key={beat.beatId} from={from} durationInFrames={dur}>
            <OffthreadVideo
              src={fileUrl(beat.sourcePath)}
              startFrom={startFrom}
              endAt={endAt}
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
        <Audio src={fileUrl(plan.voiceoverStaticPath)} />
      ) : null}

      {hook ? (
        <Sequence from={0} durationInFrames={secondsToFrames(Math.min(3, plan.durationSec), fps)}>
          <div
            style={{
              position: 'absolute',
              top: 132,
              left: 52,
              right: 52,
              color: 'white',
              fontFamily: 'Inter, Helvetica, Arial, sans-serif',
              fontSize: 52,
              fontWeight: 900,
              lineHeight: 1.18,
              textAlign: 'center',
              letterSpacing: -0.5,
              textShadow: '0 2px 0 rgba(0,0,0,0.5), 0 10px 36px rgba(0,0,0,0.55)',
              opacity: interpolate(frame, [0, 15, 40, 60], [0, 1, 1, 0], {
                extrapolateLeft: 'clamp',
                extrapolateRight: 'clamp',
              }),
            }}
          >
            {hook}
          </div>
        </Sequence>
      ) : null}

      <WordCaption activeWord={activeWord} />
    </AbsoluteFill>
  );
};

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="AiShort"
      component={AiShortComposition}
      width={WIDTH}
      height={HEIGHT}
      fps={FPS}
      durationInFrames={secondsToFrames(EMPTY_PLAN.durationSec, FPS)}
      defaultProps={EMPTY_PLAN}
      calculateMetadata={({ props }) => {
        const p = props as RenderPlanProps;
        const dur = p.durationSec ?? EMPTY_PLAN.durationSec;
        return {
          durationInFrames: secondsToFrames(dur, FPS),
          fps: FPS,
          width: WIDTH,
          height: HEIGHT,
        };
      }}
    />
  );
};

registerRoot(RemotionRoot);
