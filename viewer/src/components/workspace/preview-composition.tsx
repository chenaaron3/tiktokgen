import { AiShortComposition, FPS, HEIGHT, WIDTH } from "@remotion-shared/compositions/ai-short-composition"

import type { RenderPlan } from "@/types/vlm"

export const PREVIEW_FPS = FPS
export const PREVIEW_WIDTH = WIDTH
export const PREVIEW_HEIGHT = HEIGHT

export function RenderPlanPreviewComposition({ plan }: { plan: RenderPlan }) {
  return (
    <AiShortComposition
      durationSec={plan.durationSec}
      voiceoverStaticPath={plan.voiceoverStaticPath}
      theme={plan.theme ?? undefined}
      beats={plan.beats}
      words={plan.words}
      mediaSourceMode="api-media"
    />
  )
}
