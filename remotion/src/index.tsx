import {
  AbsoluteFill,
  Composition,
  OffthreadVideo,
  Sequence,
  interpolate,
  registerRoot,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

type Crop = {
  x: number;
  y: number;
  scale: number;
};

type Segment = {
  id: string;
  sourcePath: string;
  sourceStartSec: number;
  sourceEndSec: number;
  timelineStartSec: number;
  timelineEndSec: number;
  crop?: Crop;
};

type TextOverlay = {
  id: string;
  text: string;
  timelineStartSec: number;
  timelineEndSec: number;
  position: 'top' | 'center' | 'bottom';
};

type EditPlan = {
  durationSec: number;
  theme?: {
    title?: string;
    hookText?: string;
  };
  segments?: Segment[];
  text?: TextOverlay[];
};

const WIDTH = 1080;
const HEIGHT = 1920;
const FPS = 30;
const DEFAULT_PLAN: EditPlan = {
  durationSec: 35,
  theme: { title: 'AI Shorts Editor', hookText: 'AI Shorts Editor' },
  segments: [],
  text: [],
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

const secondsToFrames = (seconds: number, fps: number) => Math.max(0, Math.round(seconds * fps));

const overlayPosition = (position: TextOverlay['position']) => {
  if (position === 'top') {
    return { top: 160 };
  }
  if (position === 'center') {
    return { top: '45%' };
  }
  return { bottom: 210 };
};

const TextCard: React.FC<{
  children: React.ReactNode;
  position?: TextOverlay['position'];
}> = ({ children, position = 'bottom' }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 8, 45, 58], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <div
      style={{
        position: 'absolute',
        left: 72,
        right: 72,
        ...overlayPosition(position),
        opacity,
        color: 'white',
        fontFamily: 'Inter, Helvetica, Arial, sans-serif',
        fontSize: 58,
        fontWeight: 700,
        lineHeight: 1.02,
        letterSpacing: -1.6,
        textShadow: '0 8px 32px rgba(0,0,0,0.65)',
      }}
    >
      {children}
    </div>
  );
};

const PlanVideo: React.FC<EditPlan> = (plan) => {
  const { fps } = useVideoConfig();
  const segments = [...(plan.segments ?? [])].sort((a, b) => a.timelineStartSec - b.timelineStartSec);
  const overlays = plan.text ?? [];
  const hookText = plan.theme?.hookText || plan.theme?.title;

  return (
    <AbsoluteFill style={{ backgroundColor: 'black' }}>
      {segments.map((segment) => {
        const from = secondsToFrames(segment.timelineStartSec, fps);
        const duration = secondsToFrames(segment.timelineEndSec - segment.timelineStartSec, fps);
        const startFrom = secondsToFrames(segment.sourceStartSec, fps);
        const endAt = secondsToFrames(segment.sourceEndSec, fps);
        const crop = segment.crop ?? { x: 0.5, y: 0.5, scale: 1 };

        return (
          <Sequence key={segment.id} from={from} durationInFrames={duration}>
            <OffthreadVideo
              src={fileUrl(segment.sourcePath)}
              startFrom={startFrom}
              endAt={endAt}
              muted
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                objectPosition: `${crop.x * 100}% ${crop.y * 100}%`,
                transform: `scale(${crop.scale})`,
              }}
            />
          </Sequence>
        );
      })}

      {hookText ? (
        <Sequence from={0} durationInFrames={secondsToFrames(Math.min(3.2, plan.durationSec), fps)}>
          <TextCard position="bottom">{hookText}</TextCard>
        </Sequence>
      ) : null}

      {overlays.map((overlay) => (
        <Sequence
          key={overlay.id}
          from={secondsToFrames(overlay.timelineStartSec, fps)}
          durationInFrames={secondsToFrames(overlay.timelineEndSec - overlay.timelineStartSec, fps)}
        >
          <TextCard position={overlay.position}>{overlay.text}</TextCard>
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="AiShort"
      component={PlanVideo}
      width={WIDTH}
      height={HEIGHT}
      fps={FPS}
      durationInFrames={secondsToFrames(DEFAULT_PLAN.durationSec, FPS)}
      defaultProps={DEFAULT_PLAN}
      calculateMetadata={({ props }) => {
        const typedProps = props as EditPlan;
        const durationSec = typedProps.durationSec ?? DEFAULT_PLAN.durationSec;
        return {
          durationInFrames: secondsToFrames(durationSec, FPS),
          fps: FPS,
          width: WIDTH,
          height: HEIGHT,
        };
      }}
    />
  );
};

registerRoot(RemotionRoot);
