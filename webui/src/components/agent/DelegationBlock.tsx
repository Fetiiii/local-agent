import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Check, ChevronRight, Loader2, Users } from 'lucide-react'
import { cn } from '@/lib/utils'
import { agentLabel } from './toolMeta'

interface DelegationBlockProps {
  agent: string
  task?: string
  running: boolean
  children: ReactNode
}

/** A sub-agent's work, delegated by the manager. Rendered as an indented, patina-
 *  accented block (manager uses copper) so it's clear these steps belong to
 *  another actor. Open while running, auto-collapses when done. */
export function DelegationBlock({ agent, task, running, children }: DelegationBlockProps) {
  const [open, setOpen] = useState(running)
  const prev = useRef(running)
  useEffect(() => {
    if (prev.current && !running) setOpen(false)
    else if (!prev.current && running) setOpen(true)
    prev.current = running
  }, [running])

  return (
    <div className="ml-3 overflow-hidden rounded-xl border border-border border-l-2 border-l-patina bg-patina-soft/40">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-[13px]"
      >
        <ChevronRight size={14} className={cn('shrink-0 text-muted transition-transform', open && 'rotate-90')} />
        <Users size={14} className="shrink-0 text-patina" />
        <span className="shrink-0 font-medium text-text">Delegasyon →</span>
        <span className="shrink-0 font-medium text-patina">{agentLabel(agent)}</span>
        {task && <span className="min-w-0 flex-1 truncate text-muted">· {task}</span>}
        <span className={cn(task ? '' : 'ml-auto', 'shrink-0')}>
          {running ? <Loader2 size={13} className="spin text-patina" /> : <Check size={13} className="text-patina" />}
        </span>
      </button>
      {open && <div className="space-y-2 border-t border-border/60 px-3 py-2.5">{children}</div>}
    </div>
  )
}
