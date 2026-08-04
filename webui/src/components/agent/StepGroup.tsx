import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Brain, Check, ChevronRight, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { TimelineItem } from '@/lib/types'
import { toolMeta } from './toolMeta'
import { ToolCard } from './ToolCard'
import { TerminalBlock } from './TerminalBlock'
import { ApprovalCard } from './ApprovalCard'
import { NoticeLine } from './NoticeLine'
import { DelegationBlock } from './DelegationBlock'

type StepItem = Extract<TimelineItem, { kind: 'step' }>
type NonStep = Exclude<TimelineItem, { kind: 'step' }>
type ToolItem = Extract<TimelineItem, { kind: 'tool' }>

export function renderTimelineItem(item: NonStep): ReactNode {
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

// ── Delegation grouping (orchestration / multi-agent) ────────────────────────
// The backend brackets a sub-agent's work with a `delegate` tool + "🤝 …delege
// edildi" / "✅ … tamamladı" notices (no new event types). We fold those markers
// into an indented DelegationBlock so the sub-agent's steps read as its own.

// Plain booleans (not type predicates) so their false-branches don't wrongly
// narrow away other notice/tool kinds. Access fields via the typed helpers below.
const noticeText = (t: NonStep) => (t.kind === 'notice' ? t.text : '')
const isDelegateTool = (t: NonStep) => t.kind === 'tool' && (t as ToolItem).name === 'delegate'
const isStartNotice = (t: NonStep) => t.kind === 'notice' && t.text.includes('🤝') && /delege/i.test(t.text)
const isEndNotice = (t: NonStep) => t.kind === 'notice' && t.text.includes('✅') && /tamamlad/i.test(t.text)

const delegAgent = (t: NonStep) => String((t as ToolItem).args?.agent ?? '')
const delegTask = (t: NonStep) => {
  const task = (t as ToolItem).args?.task
  return task ? String(task) : undefined
}

function parseStartNotice(text: string): { agent: string; task?: string } {
  const m = text.match(/🤝\s*(\S+?)['’]?[ae]\s+delege edildi:?\s*(.*)/i)
  if (m) return { agent: m[1], task: m[2]?.trim() || undefined }
  return { agent: '' }
}

interface DelegNode {
  t: 'deleg'
  id: string
  agent: string
  task?: string
  items: NonStep[]
  running: boolean
  _end: boolean
  _deleg: ToolItem | null
}
type ChildNode = { t: 'item'; item: NonStep } | DelegNode

function groupDelegations(items: NonStep[]): ChildNode[] {
  const out: ChildNode[] = []
  let cur: DelegNode | null = null
  for (const item of items) {
    if (!cur && (isStartNotice(item) || isDelegateTool(item))) {
      cur = { t: 'deleg', id: item.id, agent: '', task: undefined, items: [], running: true, _end: false, _deleg: null }
      if (isDelegateTool(item)) {
        cur.agent = delegAgent(item)
        cur.task = delegTask(item)
        cur._deleg = item as ToolItem
      } else {
        const p = parseStartNotice(noticeText(item))
        cur.agent = p.agent
        cur.task = p.task
      }
      out.push(cur)
      continue
    }
    if (cur) {
      if (isEndNotice(item)) {
        cur._end = true
        cur = null
        continue
      }
      if (isDelegateTool(item)) {
        if (!cur.agent) cur.agent = delegAgent(item)
        if (!cur.task) cur.task = delegTask(item)
        cur._deleg = item as ToolItem
        continue
      }
      if (isStartNotice(item)) {
        if (!cur.agent) {
          const p = parseStartNotice(noticeText(item))
          cur.agent = p.agent
          cur.task = cur.task ?? p.task
        }
        continue
      }
      cur.items.push(item)
    } else {
      out.push({ t: 'item', item })
    }
  }
  for (const n of out) {
    if (n.t === 'deleg') n.running = n._end ? false : n._deleg ? n._deleg.status !== 'done' : true
  }
  return out
}

/** Render a step's children with sub-agent delegations folded into blocks. */
export function renderChildren(items: NonStep[]): ReactNode[] {
  return groupDelegations(items).map((n) =>
    n.t === 'item' ? (
      renderTimelineItem(n.item)
    ) : (
      <DelegationBlock key={n.id} agent={n.agent} task={n.task} running={n.running}>
        {n.items.map(renderTimelineItem)}
      </DelegationBlock>
    ),
  )
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
          {renderChildren(items)}
        </div>
      )}
    </div>
  )
}
