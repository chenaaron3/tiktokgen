import { ChevronRight } from 'lucide-react';
import { useEffect } from 'react';

import { ClipWorkspace } from '@/components/clip-workspace';
import { PreviewWorkspace } from '@/components/preview-workspace';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import { findClipById, useViewerStore } from '@/store/viewer-store';

export function AppLayout() {
  const fetchRuns = useViewerStore((s) => s.fetchRuns)
  const runs = useViewerStore((s) => s.runs)
  const runsLoading = useViewerStore((s) => s.runsLoading)
  const runsError = useViewerStore((s) => s.runsError)
  const view = useViewerStore((s) => s.view)
  const openRun = useViewerStore((s) => s.openRun)
  const closeRun = useViewerStore((s) => s.closeRun)
  const clipsSorted = useViewerStore((s) => s.clipsSorted)
  const selectedClipId = useViewerStore((s) => s.selectedClipId)
  const selectClip = useViewerStore((s) => s.selectClip)
  const analysisLoading = useViewerStore((s) => s.analysisLoading)
  const analysisError = useViewerStore((s) => s.analysisError)
  const selectedRunId = useViewerStore((s) => s.selectedRunId)
  const analysis = useViewerStore((s) => s.analysis)
  const renderPlan = useViewerStore((s) => s.renderPlan)
  const previewAvailable = useViewerStore((s) => s.previewAvailable)
  const workspaceTab = useViewerStore((s) => s.workspaceTab)
  const setWorkspaceTab = useViewerStore((s) => s.setWorkspaceTab)

  useEffect(() => {
    void fetchRuns()
  }, [fetchRuns])

  return (
    <div className="flex h-svh bg-zinc-950 text-zinc-50">
      <aside className="flex w-[320px] shrink-0 flex-col border-r border-zinc-800 bg-zinc-900/85">
        <div className="border-b border-zinc-800 px-4 py-3">
          <h1 className="text-sm font-semibold tracking-tight">VLM cache viewer</h1>
          <p className="text-xs text-zinc-500">Runs from ./cache • localhost only</p>
        </div>

        <ScrollArea className="flex-1">
          <div className="p-2">
            {view === "clips" ? (
              <div className="space-y-2">
                <Button variant="ghost" size="sm" className="-ml-1 w-full justify-start gap-1" onClick={() => closeRun()}>
                  <span className="text-zinc-500">←</span> Runs
                </Button>
                <Separator className="opacity-70" />
                <div
                  className={cn(
                    "grid gap-1 rounded-md border border-zinc-800 bg-zinc-900 p-1",
                    previewAvailable ? "grid-cols-2" : "grid-cols-1",
                  )}
                >
                  <button
                    type="button"
                    onClick={() => setWorkspaceTab("clips")}
                    className={cn(
                      "rounded px-2 py-1 text-xs font-medium transition-colors",
                      workspaceTab === "clips" ? "bg-zinc-700 text-zinc-50" : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200",
                    )}
                  >
                    Clips
                  </button>
                  {previewAvailable ? (
                    <button
                      type="button"
                      onClick={() => setWorkspaceTab("preview")}
                      className={cn(
                        "rounded px-2 py-1 text-xs font-medium transition-colors",
                        workspaceTab === "preview"
                          ? "bg-zinc-700 text-zinc-50"
                          : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200",
                      )}
                    >
                      Preview
                    </button>
                  ) : null}
                </div>
                <p className="px-2 text-xs font-medium uppercase tracking-wide text-zinc-500">Clips</p>
                {analysisLoading ? (
                  <p className="px-2 text-xs text-zinc-500">Loading…</p>
                ) : analysisError ? (
                  <p className="px-2 text-xs text-red-400">{analysisError}</p>
                ) : (
                  <ul className="space-y-0.5">
                    {clipsSorted.map((clip) => {
                      const id = clip.id ?? clip.originalFilename ?? "clip"
                      const active = selectedClipId === id
                      return (
                        <li key={id}>
                          <button
                            type="button"
                            onClick={() => selectClip(id)}
                            className={cn(
                              "flex w-full items-center gap-1 rounded-md px-2 py-2 text-left text-sm transition-colors",
                              active ? "bg-zinc-800 text-zinc-50" : "hover:bg-zinc-800/50",
                            )}
                          >
                            <ChevronRight className="size-3 shrink-0 opacity-50" aria-hidden />
                            <span className="truncate">{clip.originalFilename ?? id}</span>
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </div>
            ) : (
              <>
                {runsLoading && <p className="px-2 py-4 text-xs text-zinc-500">Loading runs…</p>}
                {runsError && <p className="px-2 py-4 text-xs text-red-400">{runsError}</p>}
                {!runsLoading && runs.length === 0 && (
                  <p className="px-2 py-4 text-xs text-zinc-500">No runs with vlm-analysis.json.</p>
                )}
                <ul className="space-y-0.5">
                  {runs.map((r) => (
                    <li key={r.runId}>
                      <button
                        type="button"
                        className={cn(
                          "w-full rounded-md px-3 py-2 text-left transition-colors hover:bg-zinc-800/60",
                          selectedRunId === r.runId ? "bg-zinc-800" : "",
                        )}
                        onClick={() => void openRun(r.runId)}
                      >
                        <div className="break-all font-mono text-xs leading-tight">{r.runId}</div>
                        <div className="mt-1 flex justify-between gap-2 text-[11px] text-zinc-500">
                          <span className="truncate">{r.analyzedAt ?? "—"}</span>
                          <span className="shrink-0">{r.clipCount} clips</span>
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        </ScrollArea>
      </aside>

      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        {workspaceTab === "preview" && previewAvailable ? (
          <PreviewWorkspace analysis={analysis} renderPlan={renderPlan} />
        ) : (
          <ClipWorkspace
            key={`${selectedRunId ?? ""}:${selectedClipId ?? ""}`}
            clip={findClipById(clipsSorted, selectedClipId)}
          />
        )}
      </main>
    </div>
  )
}
