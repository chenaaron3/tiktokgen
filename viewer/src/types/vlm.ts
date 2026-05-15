/** VLM analysis JSON from cache (camelCase keys). */

export type LabelConfidence = "low" | "medium" | "high"
export type VerifiedBy = "twelvelabs" | "gpt"

export type MediaOrientation = "horizontal" | "vertical" | "square" | "unknown"

export interface GeoLocation {
  latitude?: number
  longitude?: number
  raw?: string
  source?: string
  altitude?: number
}

export interface CaptureMetadata {
  capturedAt?: string | null
  location?: GeoLocation | null
}

export interface ClipMedia {
  durationSec?: number | null
  width?: number | null
  height?: number | null
  fps?: number | null
  hasAudio?: boolean | null
  orientation?: MediaOrientation
  captureMetadata?: CaptureMetadata
}

export interface IdentifiedShot {
  shotId?: string
  startSec?: number
  endSec?: number
  vlmTag?: string
  keyInstantStartSec?: number
  dishName?: string | null
  reasoning?: string
  semanticContext?: string | null
  labelConfidence?: LabelConfidence
  verifiedBy?: VerifiedBy
}

export interface VlmClip {
  id?: string
  sourcePath?: string
  originalFilename?: string
  durationSec?: number | null
  capturedAt?: string | null
  summary?: string
  identifiedShots?: IdentifiedShot[] | null
  media?: ClipMedia | null
  location?: GeoLocation | null
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
  overlayText?: string
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
