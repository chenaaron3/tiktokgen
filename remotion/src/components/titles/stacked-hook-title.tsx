import type { CSSProperties } from 'react';
import { interpolate, useCurrentFrame, useVideoConfig } from 'remotion';

import { WordRevealLine } from './word-reveal-line';

type StackedHookTitleProps = {
  text: string;
  durationInFrames: number;
};

const splitWordsIntoLines = (words: string[], lineCount: number): string[][] => {
  if (words.length === 0) return [];
  const lines: string[][] = [];
  const wordsPerLine = Math.max(1, Math.ceil(words.length / lineCount));
  for (let i = 0; i < words.length; i += wordsPerLine) {
    lines.push(words.slice(i, i + wordsPerLine));
  }
  return lines;
};

const lineStyles: CSSProperties[] = [
  {
    fontFamily: '"Playfair Display", Georgia, serif',
    fontSize: 84,
    fontWeight: 700,
    lineHeight: 1,
  },
  {
    fontFamily: '"Playfair Display", Georgia, serif',
    fontSize: 112,
    fontWeight: 800,
    lineHeight: 0.92,
  },
  {
    fontFamily: '"Pacifico", "Brush Script MT", cursive',
    fontSize: 104,
    fontWeight: 600,
    lineHeight: 0.96,
    letterSpacing: 0.5,
  },
  {
    fontFamily: '"Bebas Neue", Impact, sans-serif',
    fontSize: 116,
    fontWeight: 700,
    lineHeight: 0.95,
    letterSpacing: 2,
    textTransform: 'uppercase',
  },
];

export const StackedHookTitle: React.FC<StackedHookTitleProps> = ({ text, durationInFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const words = text.trim().split(/\s+/).filter(Boolean);
  const lines = splitWordsIntoLines(words, 4);

  if (lines.length === 0) return null;

  const fadeOutStart = Math.max(18, durationInFrames - 12);
  const opacity = interpolate(frame, [0, 15, fadeOutStart, durationInFrames], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  let wordOffset = 0;

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'flex-start',
        alignItems: 'center',
        textAlign: 'center',
        color: 'rgba(255,255,255,0.96)',
        textShadow: '0 4px 20px rgba(0,0,0,0.7)',
        padding: '132px 56px 0',
        transform: `scale(${interpolate(frame, [0, 10], [0.97, 1], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        })})`,
      }}
    >
      {lines.map((lineWords, i) => {
        const startWordIndex = wordOffset;
        wordOffset += lineWords.length;

        return (
          <WordRevealLine
            key={`line-${i}`}
            words={lineWords}
            startWordIndex={startWordIndex}
            fps={fps}
            frame={frame}
            globalOpacity={opacity}
            style={{ marginTop: i === 0 ? 0 : 8 }}
            wordStyle={lineStyles[Math.min(i, lineStyles.length - 1)]}
          />
        );
      })}
    </div>
  );
};
