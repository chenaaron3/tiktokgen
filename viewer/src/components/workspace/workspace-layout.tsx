import type { ReactNode } from "react"

export function WorkspaceLayout({
  player,
  metadata,
  timeline,
}: {
  player: ReactNode
  metadata: ReactNode
  timeline: ReactNode
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex min-h-0 min-w-0 flex-1 flex-row">
        <div className="flex min-h-0 min-w-0 flex-1 basis-0 flex-col border-r border-zinc-800 p-3">{player}</div>
        <div className="flex min-h-0 min-w-0 flex-1 basis-0 flex-col p-3 pl-4">{metadata}</div>
      </div>
      {timeline}
    </div>
  )
}
