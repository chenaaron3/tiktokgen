import type { CSSProperties } from 'react';
import { interpolate } from 'remotion';

type WordRevealLineProps = {
  words: string[];
  startWordIndex?: number;
  fps: number;
  frame: number;
  globalOpacity?: number;
  delaySec?: number;
  style?: CSSProperties;
  wordStyle?: CSSProperties;
};

export const WordRevealLine: React.FC<WordRevealLineProps> = ({
  words,
  startWordIndex = 0,
  fps,
  frame,
  globalOpacity = 1,
  delaySec = 0.25,
  style,
  wordStyle,
}) => {
  if (words.length === 0) return null;
  const delayFrames = Math.max(1, Math.round(delaySec * fps));

  return (
    <div style={style}>
      {words.map((word, i) => {
        const start = (startWordIndex + i) * delayFrames;
        const wordOpacity =
          interpolate(frame, [start, start + 6], [0, 1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          }) * globalOpacity;
        const translateY = interpolate(frame, [start, start + 8], [14, 0], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });

        return (
          <span
            key={`${word}-${startWordIndex + i}`}
            style={{
              display: 'inline-block',
              whiteSpace: 'pre',
              opacity: wordOpacity,
              transform: `translateY(${translateY}px)`,
              ...wordStyle,
            }}
          >
            {word}
            {i < words.length - 1 ? ' ' : ''}
          </span>
        );
      })}
    </div>
  );
};
