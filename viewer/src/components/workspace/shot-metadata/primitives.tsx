import type { ReactNode } from "react"

import { confidenceBadgeClass } from "@/lib/shot-label-meta"
import { cn } from "@/lib/utils"
import type { IdentifiedShot } from "@/types/vlm"

export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h2 className="m-0 text-[11px] font-semibold uppercase tracking-wide text-zinc-500">{children}</h2>
  )
}

export function MetadataRow({
  label,
  value,
  mono,
  clamp,
}: {
  label: string
  value: string
  mono?: boolean
  clamp?: number
}) {
  return (
    <>
      <dt className="shrink-0 leading-snug text-zinc-500">{label}</dt>
      <dd
        title={value !== "—" ? value : undefined}
        className={cn(
          "m-0 min-w-0 leading-snug text-zinc-300",
          mono && "break-all font-mono text-[11px]",
          !mono && "break-words",
          clamp === 2 && "line-clamp-2",
          clamp === 3 && "line-clamp-3",
        )}
      >
        {value}
      </dd>
    </>
  )
}

export function ProseRow({
  label,
  text,
  highlight,
}: {
  label: string
  text: string
  highlight?: boolean
}) {
  return (
    <div
      className="grid min-w-0 items-start gap-x-2.5"
      style={{ gridTemplateColumns: "4.75rem minmax(0, 1fr)" }}
    >
      <span className="shrink-0 leading-snug text-zinc-500">{label}</span>
      <p
        className={cn(
          "m-0 min-w-0 leading-snug",
          highlight ? "text-sky-200/90" : "text-zinc-400",
        )}
      >
        {text}
      </p>
    </div>
  )
}

export function FactSeparator() {
  return (
    <span className="select-none text-zinc-600" aria-hidden>
      {" "}
      ·{" "}
    </span>
  )
}

export function ConfidenceBadge({ confidence }: { confidence: IdentifiedShot["labelConfidence"] }) {
  const label = confidence ?? "unknown"
  return (
    <span
      className={cn(
        "inline-flex rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        confidenceBadgeClass(confidence),
      )}
    >
      {label}
    </span>
  )
}
