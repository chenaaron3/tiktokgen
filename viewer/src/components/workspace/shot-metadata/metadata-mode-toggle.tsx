import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

export type ShotMetadataPanelMode = "shot" | "planning"

export function MetadataModeToggle({
  mode,
  onModeChange,
}: {
  mode: ShotMetadataPanelMode
  onModeChange: (mode: ShotMetadataPanelMode) => void
}) {
  return (
    <div
      role="tablist"
      aria-label="Metadata view"
      className="grid grid-cols-2 gap-1 rounded-md border border-zinc-800 bg-zinc-950/60 p-1"
    >
      <ModeTab active={mode === "shot"} onClick={() => onModeChange("shot")}>
        Shot data
      </ModeTab>
      <ModeTab active={mode === "planning"} onClick={() => onModeChange("planning")}>
        LLM planning
      </ModeTab>
    </div>
  )
}

function ModeTab({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        "rounded px-2 py-1 text-[11px] font-medium transition-colors",
        active ? "bg-zinc-700 text-zinc-50" : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200",
      )}
    >
      {children}
    </button>
  )
}
