import type { TimelineItem } from '@/lib/types'
import { StepGroup, renderTimelineItem } from './StepGroup'

type StepItem = Extract<TimelineItem, { kind: 'step' }>
type NonStep = Exclude<TimelineItem, { kind: 'step' }>
interface Group {
  step: StepItem | null
  items: NonStep[]
}

export function Timeline({ items, turnDone }: { items: TimelineItem[]; turnDone: boolean }) {
  if (!items.length) return null

  // Group each thought with the tool runs that follow it, up to the next thought.
  const groups: Group[] = []
  let cur: Group | null = null
  for (const it of items) {
    if (it.kind === 'step') {
      cur = { step: it, items: [] }
      groups.push(cur)
    } else {
      if (!cur) {
        cur = { step: null, items: [] }
        groups.push(cur)
      }
      cur.items.push(it)
    }
  }

  let stepNo = 0
  return (
    <div className="space-y-2">
      {groups.map((g, i) => {
        const isLast = i === groups.length - 1
        const active = g.step?.streaming || (isLast && !turnDone)
        // A group with no thought (e.g. a stray notice) renders flat, no chrome.
        if (!g.step) return g.items.map(renderTimelineItem)
        stepNo += 1
        return <StepGroup key={g.step.id} index={stepNo} step={g.step} items={g.items} active={!!active} />
      })}
    </div>
  )
}
