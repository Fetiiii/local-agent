import { useState, type ReactNode } from 'react'
import { Check, Loader2, Minus, PanelRight, Plus, X } from 'lucide-react'
import { useStore } from '@/lib/store'
import { cn } from '@/lib/utils'
import type { TimelineItem } from '@/lib/types'

type TerminalItem = Extract<TimelineItem, { kind: 'terminal' }>

function Dot({ color, title, glyph, onClick }: { color: string; title: string; glyph: ReactNode; onClick: () => void }) {
  return (
    <button
      onClick={(e) => {
        e.stopPropagation()
        onClick()
      }}
      title={title}
      className="group/dot flex h-3 w-3 items-center justify-center rounded-full transition-transform hover:scale-110"
      style={{ background: color }}
    >
      <span className="text-black/60 opacity-0 transition-opacity group-hover/dot:opacity-100">{glyph}</span>
    </button>
  )
}

export function TerminalBlock({ item }: { item: TerminalItem }) {
  const openArtifact = useStore((s) => s.openArtifact)
  const [collapsed, setCollapsed] = useState(false)
  const running = item.status === 'running'

  return (
    <div className="overflow-hidden rounded-lg border border-border-strong bg-terminal-bg font-mono text-[12.5px]">
      <div
        className="flex cursor-pointer items-center gap-2 border-b border-border/50 bg-black/20 px-3 py-1.5"
        onClick={() => setCollapsed((c) => !c)}
      >
        <span className="flex gap-1.5">
          <Dot color="#e5654b" title="Kapat / küçült" glyph={<X size={7} strokeWidth={3} />} onClick={() => setCollapsed(true)} />
          <Dot color="#e0a54a" title="Küçült" glyph={<Minus size={7} strokeWidth={3} />} onClick={() => setCollapsed(true)} />
          <Dot color="#5bb8a8" title="Genişlet" glyph={<Plus size={7} strokeWidth={3} />} onClick={() => setCollapsed(false)} />
        </span>
        <span className="ml-1 truncate text-[11px] uppercase tracking-wide text-muted">
          terminal{item.cwd ? ` · ${item.cwd}` : ''}
        </span>
        {collapsed && item.command && (
          <span className="min-w-0 flex-1 truncate text-[11.5px] text-muted/80">
            <span className="text-patina">$ </span>
            {item.command}
          </span>
        )}
        <span className={cn('ml-auto', collapsed && 'ml-2')}>
          {running ? <Loader2 size={13} className="spin text-accent" /> : <Check size={13} className="text-patina" />}
        </span>
      </div>

      {!collapsed && (
        <>
          <div className="max-h-80 overflow-auto p-3 leading-relaxed">
            <div className="flex gap-2">
              <span className="select-none text-patina">$</span>
              <span className="whitespace-pre-wrap break-all text-text">{item.command}</span>
            </div>
            {item.output != null && item.output !== '' && (
              <pre className="mt-1.5 whitespace-pre-wrap break-all text-muted">{item.output}</pre>
            )}
            {running && <span className="mt-1 inline-block h-3.5 w-2 animate-pulse bg-accent align-middle" />}
          </div>
          {item.artifactIds.length > 0 && (
            <div className="border-t border-border/50 px-3 py-1.5">
              <button
                onClick={() => openArtifact(item.artifactIds[0])}
                className="inline-flex items-center gap-1.5 text-[12px] text-accent hover:text-accent-hover"
              >
                <PanelRight size={13} /> {item.artifactIds.length} sonuç panelde
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
