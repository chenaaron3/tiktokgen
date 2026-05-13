/** VLM analysis JSON from cache (camelCase keys). */

export interface IdentifiedShot {
  shotId?: string
  startSec?: number
  endSec?: number
  vlmTag?: string
  keyInstantStartSec?: number
  dishName?: string | null
  reasoning?: string
}

export interface VlmClip {
  id?: string
  sourcePath?: string
  originalFilename?: string
  durationSec?: number | null
  capturedAt?: string | null
  summary?: string
  identifiedShots?: IdentifiedShot[] | null
  media?: { durationSec?: number | null; width?: number; height?: number; fps?: number } | null
  location?: { latitude?: number; longitude?: number } | null
}

export interface VlmAnalysis {
  runId?: string
  analyzedAt?: string
  clips?: VlmClip[] | null
  provider?: Record<string, unknown>
}

export interface ShotRef {
  clipId: string
  shotId: string
  beatSpan: number
  reasoning: string
}

export interface ShotMatchAssignment {
  sentenceId: string
  text: string
  shots: ShotRef[]
}

export interface ShotMatch {
  _planning?: string
  assignments: ShotMatchAssignment[]
}

export interface RenderWord {
  word: string
  startSec: number
  endSec: number
}

export interface RenderBeat {
  beatId: string
  sentenceId: string
  clipId: string
  shotId: string
  sourcePath: string
  sourceStartSec: number
  sourceEndSec: number
  timelineStartSec: number
  timelineEndSec: number
}

export interface RenderTheme {
  hookText?: string
}

export interface RenderPlan {
  runId?: string
  createdAt?: string
  durationSec: number
  voiceoverStaticPath: string
  theme?: RenderTheme | null
  beats: RenderBeat[]
  words: RenderWord[]
  assumptions?: string[]
  warnings?: string[]
}
