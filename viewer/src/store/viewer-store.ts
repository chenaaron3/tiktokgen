import { create } from "zustand"

import type { RenderPlan, ShotMatch, VlmAnalysis, VlmClip } from "@/types/vlm"

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
  shotMatch: ShotMatch | null
  renderPlan: RenderPlan | null
  previewAvailable: boolean
  analysisLoading: boolean
  analysisError: string | null
  clipsSorted: VlmClip[]
  workspaceTab: "clips" | "preview"

  selectedClipId: string | null

  openRun: (runId: string) => Promise<void>
  closeRun: () => void

  selectClip: (clipId: string | null) => void
  setWorkspaceTab: (tab: "clips" | "preview") => void
}

async function fetchJsonOrNull<T>(url: string): Promise<T | null> {
  const res = await fetch(url)
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return (await res.json()) as T
}

export const useViewerStore = create<ViewerState>((set) => ({
  runs: [],
  runsError: null,
  runsLoading: false,

  selectedRunId: null,
  view: "runs",
  analysis: null,
  shotMatch: null,
  renderPlan: null,
  previewAvailable: false,
  analysisLoading: false,
  analysisError: null,
  clipsSorted: [],
  workspaceTab: "clips",

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
      shotMatch: null,
      renderPlan: null,
      previewAvailable: false,
      clipsSorted: [],
      selectedClipId: null,
      workspaceTab: "clips",
    })
    try {
      const encodedRunId = encodeURIComponent(runId)
      const [analysis, shotMatch, renderPlan] = await Promise.all([
        fetchJsonOrNull<VlmAnalysis>(`/api/run/${encodedRunId}/analysis`),
        fetchJsonOrNull<ShotMatch>(`/api/run/${encodedRunId}/shot-match`),
        fetchJsonOrNull<RenderPlan>(`/api/run/${encodedRunId}/render-plan`),
      ])
      if (!analysis) {
        throw new Error("analysis not found")
      }
      const clipsSorted = sortedClips(analysis.clips ?? [])
      const firstId = clipsSorted[0]?.id ?? null
      set({
        analysis,
        shotMatch,
        renderPlan,
        previewAvailable: Boolean(
          shotMatch?.assignments?.length && renderPlan?.beats?.length,
        ),
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
      shotMatch: null,
      renderPlan: null,
      previewAvailable: false,
      analysisError: null,
      clipsSorted: [],
      selectedClipId: null,
      analysisLoading: false,
      workspaceTab: "clips",
    }),

  selectClip: (clipId: string | null) => set({ selectedClipId: clipId }),
  setWorkspaceTab: (tab) => set({ workspaceTab: tab }),
}))

export function findClipById(sorted: VlmClip[], id: string | null): VlmClip | null {
  if (!id) return null
  return sorted.find((c) => c.id === id) ?? null
}
