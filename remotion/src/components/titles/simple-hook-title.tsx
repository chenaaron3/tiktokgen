import { interpolate, useCurrentFrame, useVideoConfig } from 'remotion';

import { WordRevealLine } from './word-reveal-line';

type SimpleHookTitleProps = {
  text: string;
  durationInFrames: number;
};

export const SimpleHookTitle: React.FC<SimpleHookTitleProps> = ({ text, durationInFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const words = text.trim().split(/\s+/).filter(Boolean);

  if (words.length === 0) return null;

  const fadeOutStart = Math.max(18, durationInFrames - 12);
  const opacity = interpolate(frame, [0, 15, fadeOutStart, durationInFrames], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <WordRevealLine
      words={words}
      fps={fps}
      frame={frame}
      globalOpacity={opacity}
      style={{
        position: 'absolute',
        top: 132,
        left: 52,
        right: 52,
        textAlign: 'center',
      }}
      wordStyle={{
        color: 'white',
        fontFamily: 'Inter, Helvetica, Arial, sans-serif',
        fontSize: 52,
        fontWeight: 900,
        lineHeight: 1.18,
        letterSpacing: -0.5,
        textShadow: '0 2px 0 rgba(0,0,0,0.5), 0 10px 36px rgba(0,0,0,0.55)',
      }}
    />
  );
};
