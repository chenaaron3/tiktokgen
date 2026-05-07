import { create } from "zustand"

import type { VlmAnalysis, VlmClip } from "@/types/vlm"

export interface RunSummary {
  runId: string
  analyzedAt: string | null
  clipCount: number
}

function clipCapturedSortKey(iso: string | null | undefined): number {
  if (!iso) return 0
  const ms = Date.parse(iso)
  return Number.isNaN(ms) ? 0 : ms
}

function sortedClips(clips: VlmClip[] | null | undefined): VlmClip[] {
  const list = clips?.filter(Boolean) ?? []
  return [...list].sort((a, b) => clipCapturedSortKey(a.capturedAt) - clipCapturedSortKey(b.capturedAt))
}

interface ViewerState {
  runs: RunSummary[]
  runsError: string | null
  runsLoading: boolean
  fetchRuns: () => Promise<void>

  selectedRunId: string | null
  view: "runs" | "clips"
  analysis: VlmAnalysis | null
  analysisLoading: boolean
  analysisError: string | null
  clipsSorted: VlmClip[]

  selectedClipId: string | null

  openRun: (runId: string) => Promise<void>
  closeRun: () => void

  selectClip: (clipId: string | null) => void
}

export const useViewerStore = create<ViewerState>((set) => ({
  runs: [],
  runsError: null,
  runsLoading: false,

  selectedRunId: null,
  view: "runs",
  analysis: null,
  analysisLoading: false,
  analysisError: null,
  clipsSorted: [],

  selectedClipId: null,

  fetchRuns: async () => {
    set({ runsLoading: true, runsError: null })
    try {
      const res = await fetch("/api/runs")
      if (!res.ok) {
        throw new Error(`${res.status} ${res.statusText}`)
      }
      const data = (await res.json()) as RunSummary[]
      set({ runs: Array.isArray(data) ? data : [], runsLoading: false })
    } catch (e) {
      set({
        runsError: e instanceof Error ? e.message : String(e),
        runsLoading: false,
      })
    }
  },

  openRun: async (runId: string) => {
    set({
      selectedRunId: runId,
      view: "clips",
      analysisLoading: true,
      analysisError: null,
      analysis: null,
      clipsSorted: [],
      selectedClipId: null,
    })
    try {
      const res = await fetch(`/api/run/${encodeURIComponent(runId)}/analysis`)
      if (!res.ok) {
        throw new Error(`${res.status} ${res.statusText}`)
      }
      const analysis = (await res.json()) as VlmAnalysis
      const clipsSorted = sortedClips(analysis.clips ?? [])
      const firstId = clipsSorted[0]?.id ?? null
      set({
        analysis,
        clipsSorted,
        analysisLoading: false,
        selectedClipId: firstId,
      })
    } catch (e) {
      set({
        analysisError: e instanceof Error ? e.message : String(e),
        analysisLoading: false,
      })
    }
  },

  closeRun: () =>
    set({
      view: "runs",
      selectedRunId: null,
      analysis: null,
      analysisError: null,
      clipsSorted: [],
      selectedClipId: null,
      analysisLoading: false,
    }),

  selectClip: (clipId: string | null) => set({ selectedClipId: clipId }),
}))

export function findClipById(sorted: VlmClip[], id: string | null): VlmClip | null {
  if (!id) return null
  return sorted.find((c) => c.id === id) ?? null
}
