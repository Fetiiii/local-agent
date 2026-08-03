import { Check, Loader2, PanelRight } from 'lucide-react'
import { Disclosure } from '@/components/ui/Disclosure'
import { useStore } from '@/lib/store'
import type { TimelineItem } from '@/lib/types'
import { toolMeta } from './toolMeta'

type ToolItem = Extract<TimelineItem, { kind: 'tool' }>

export function ToolCard({ item }: { item: ToolItem }) {
  const openArtifact = useStore((s) => s.openArtifact)
  const { label, Icon } = toolMeta(item.name)
  const running = item.status === 'running'
  const argStr = JSON.stringify(item.args ?? {}, null, 2)

  return (
    <Disclosure
      accent="accent"
      icon={<Icon size={14} className="text-accent" />}
      title={<span className="text-text">{label}</span>}
      meta={
        running ? (
          <Loader2 size={14} className="spin text-accent" />
        ) : (
          <Check size={14} className="text-patina" />
        )
      }
    >
      {argStr !== '{}' && (
        <pre className="mb-2 overflow-x-auto rounded-md bg-code-bg p-2 font-mono text-[12px] text-muted">
          {argStr}
        </pre>
      )}
      {item.result && (
        <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-md bg-code-bg p-2 font-mono text-[12px]">
          {item.result}
        </pre>
      )}
      {item.artifactIds.length > 0 && (
        <button
          onClick={() => openArtifact(item.artifactIds[0])}
          className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-border px-2 py-1 text-[12px] text-accent transition-colors hover:border-accent"
        >
          <PanelRight size={13} />
          {item.artifactIds.length} sonuç panelde
        </button>
      )}
    </Disclosure>
  )
}
