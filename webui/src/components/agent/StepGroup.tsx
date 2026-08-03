import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Brain, Check, ChevronRight, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { TimelineItem } from '@/lib/types'
import { toolMeta } from './toolMeta'
import { ToolCard } from './ToolCard'
import { TerminalBlock } from './TerminalBlock'
import { ApprovalCard } from './ApprovalCard'
import { NoticeLine } from './NoticeLine'

type StepItem = Extract<TimelineItem, { kind: 'step' }>

export function renderTimelineItem(item: Exclude<TimelineItem, { kind: 'step' }>): ReactNode {
  switch (item.kind) {
    case 'tool':
      return <ToolCard key={item.id} item={item} />
    case 'terminal':
      return <TerminalBlock key={item.id} item={item} />
    case 'approval':
      return <ApprovalCard key={item.id} item={item} />
    case 'notice':
      return <NoticeLine key={item.id} item={item} />
  }
}

interface StepGroupProps {
  index: number
  step: StepItem | null
  items: Exclude<TimelineItem, { kind: 'step' }>[]
  active: boolean
}

/** One agent iteration: a thought + the tools it triggered, collapsed into a
 *  single "Adım" so long tool runs don't blow up the chat vertically. */
export function StepGroup({ index, step, items, active }: StepGroupProps) {
  const streaming = !!step?.streaming
  const running =
    streaming ||
    items.some(
      (t) =>
        ((t.kind === 'tool' || t.kind === 'terminal') && t.status === 'running') ||
        (t.kind === 'approval' && t.status === 'pending'),
    )

  const [open, setOpen] = useState(active)
  const prev = useRef(active)
  useEffect(() => {
    // Auto-collapse a step once it finishes; auto-open when it becomes active.
    if (prev.current && !active) setOpen(false)
    else if (!prev.current && active) setOpen(true)
    prev.current = active
  }, [active])

  // Distinct tool icons used in this step, for the collapsed summary.
  const toolIcons = Array.from(
    new Map(
      items
        .filter((t): t is Extract<TimelineItem, { kind: 'tool' | 'terminal' }> => t.kind === 'tool' || t.kind === 'terminal')
        .map((t) => {
          const name = t.kind === 'terminal' ? 'shell_executor' : t.name
          return [name, toolMeta(name)]
        }),
    ).values(),
  )

  const preview = step?.thought ? step.thought.replace(/\s+/g, ' ').trim().slice(0, 60) : ''

  return (
    <div className={cn('overflow-hidden rounded-xl border border-border bg-panel-2/50', running && 'border-l-2 border-l-accent')}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-[13px]"
      >
        <ChevronRight size={14} className={cn('shrink-0 text-muted transition-transform', open && 'rotate-90')} />
        <span className="font-medium text-text">Adım {index}</span>
        {running ? (
          <Loader2 size={13} className="spin text-accent" />
        ) : (
          <Check size={13} className="text-patina" />
        )}
        {!open && (
          <span className="flex min-w-0 flex-1 items-center gap-1.5 text-muted">
            {toolIcons.map(({ label, Icon }) => (
              <Icon key={label} size={13} className="shrink-0 opacity-80" />
            ))}
            {preview && <span className="truncate">· {preview}…</span>}
          </span>
        )}
      </button>

      {open && (
        <div className="space-y-2 border-t border-border/60 px-3 py-2.5">
          {step?.thought && (
            <div className="rounded-lg bg-panel-2/60 px-2.5 py-2">
              <div className="mb-1 flex items-center gap-1.5 text-[12px] text-muted">
                <Brain size={13} className={streaming ? 'text-accent pulse-ring' : ''} />
                {streaming ? 'düşünüyor…' : 'düşünce'}
              </div>
              <p className="whitespace-pre-wrap text-[13px] text-muted">
                {step.thought}
                {streaming && <span className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse bg-accent align-middle" />}
              </p>
            </div>
          )}
          {items.map(renderTimelineItem)}
        </div>
      )}
    </div>
  )
}
