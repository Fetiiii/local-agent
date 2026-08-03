import { useState } from 'react'
import { Check, ChevronDown, ListChecks, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useStore } from '@/lib/store'

/** The current turn's plan, pinned above the chat (out of the message flow).
 *  Shows live progress; collapsible; hidden when there is no plan. */
export function PlanStrip() {
  const [open, setOpen] = useState(true)
  const messages = useStore((s) => s.messages)
  const busy = useStore((s) => s.busy)

  // Last assistant turn that has a plan.
  const msg = [...messages].reverse().find((m) => m.role === 'assistant' && m.plan.length > 0)
  if (!msg) return null

  const plan = msg.plan
  const done = plan.filter((p) => p.done).length
  const active = busy && !msg.done
  const currentIdx = plan.findIndex((p) => !p.done)

  return (
    <div className="mx-auto w-full max-w-3xl px-4 pt-3">
      <div className="overflow-hidden rounded-xl border border-border bg-panel-2/70 backdrop-blur">
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex w-full items-center gap-2 px-3 py-2 text-left text-[13px] font-medium text-text"
        >
          <ListChecks size={15} className="text-accent" />
          Plan
          {active && <Loader2 size={13} className="spin text-accent" />}
          <span className="ml-auto font-mono text-[11px] text-muted">
            {done}/{plan.length}
          </span>
          <ChevronDown size={15} className={cn('text-muted transition-transform', !open && '-rotate-90')} />
        </button>
        {open && (
          <ul className="space-y-1.5 border-t border-border/60 px-3 py-2.5">
            {plan.map((item, i) => {
              const isCurrent = active && i === currentIdx
              return (
                <li key={i} className="flex items-start gap-2 text-[13px]">
                  <span
                    className={cn(
                      'mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border',
                      item.done
                        ? 'border-patina bg-patina text-accent-contrast'
                        : isCurrent
                          ? 'border-accent text-accent'
                          : 'border-border-strong text-transparent',
                    )}
                  >
                    {item.done ? <Check size={11} /> : isCurrent ? <Loader2 size={11} className="spin" /> : null}
                  </span>
                  <span className={cn(item.done ? 'text-muted line-through' : isCurrent ? 'text-text' : 'text-muted')}>
                    {item.text}
                  </span>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}
