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
