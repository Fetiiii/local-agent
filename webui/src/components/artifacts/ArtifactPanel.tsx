import { X } from 'lucide-react'
import { useStore } from '@/lib/store'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/utils'
import { toolMeta } from '@/components/agent/toolMeta'
import { artifactMeta } from './artifactMeta'
import { ArtifactView } from './ArtifactView'

export function ArtifactPanel() {
  const artifacts = useStore((s) => s.artifacts)
  const activeId = useStore((s) => s.activeArtifactId)
  const openArtifact = useStore((s) => s.openArtifact)
  const closeArtifacts = useStore((s) => s.closeArtifacts)

  const active = artifacts.find((a) => a.id === activeId) ?? artifacts[artifacts.length - 1]

  return (
    <div className="flex h-full w-full flex-col">
      <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border px-4">
        <span className="text-[13px] font-semibold uppercase tracking-wide text-muted">Artifacts</span>
        <span className="rounded-full bg-panel-2 px-1.5 text-[11px] text-muted">{artifacts.length}</span>
        <div className="flex-1" />
        <Button variant="ghost" size="icon" onClick={closeArtifacts} aria-label="Paneli kapat">
          <X size={17} />
        </Button>
      </header>

      {artifacts.length > 1 && (
        <div className="flex shrink-0 gap-1.5 overflow-x-auto border-b border-border px-3 py-2">
          {artifacts.map((entry) => {
            const { label, Icon } = artifactMeta(entry.artifact)
            const isActive = entry.id === active?.id
            return (
              <button
                key={entry.id}
                onClick={() => openArtifact(entry.id)}
                title={`${toolMeta(entry.sourceTool).label} · ${label}`}
                className={cn(
                  'flex shrink-0 items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[12px] transition-colors',
                  isActive
                    ? 'border-accent bg-accent-soft text-accent'
                    : 'border-border text-muted hover:text-text',
                )}
              >
                <Icon size={13} />
                <span className="max-w-[120px] truncate">{label}</span>
              </button>
            )
          })}
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-auto p-4">
        {active ? (
          <div>
            <div className="mb-3 flex items-center gap-2 text-[12px] text-muted">
              {(() => {
                const { label, Icon } = artifactMeta(active.artifact)
                return (
                  <>
                    <Icon size={14} className="text-accent" />
                    <span className="font-medium text-text">{label}</span>
                    <span className="text-muted">· {toolMeta(active.sourceTool).label}</span>
                  </>
                )
              })()}
            </div>
            <ArtifactView artifact={active.artifact} />
          </div>
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted">Henüz artifact yok.</div>
        )}
      </div>
    </div>
  )
}
