import { Composition, registerRoot } from 'remotion';

import {
  AiShortComposition,
  EMPTY_PLAN,
  FPS,
  HEIGHT,
  WIDTH,
  secondsToFrames,
  type RenderPlanProps,
} from './compositions/ai-short-composition';

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
