import { useState } from 'react'
import { Loader2, Menu, PanelLeft, PanelRight, Plus, Settings2 } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Brand } from '@/components/layout/Brand'
import { ThemeToggle } from '@/components/layout/ThemeToggle'
import { Drawer } from '@/components/layout/Drawer'
import { SettingsDialog } from '@/components/layout/SettingsDialog'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import { MessageList } from '@/components/chat/MessageList'
import { Composer } from '@/components/chat/Composer'
import { ArtifactPanel } from '@/components/artifacts/ArtifactPanel'
import { ConversationList } from '@/components/sidebar/ConversationList'
import { PlanStrip } from '@/components/agent/PlanStrip'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useAppData } from '@/hooks/useAppData'
import { useStore } from '@/lib/store'
import { cn, shortModelName } from '@/lib/utils'

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const newChat = useStore((s) => s.newChat)
  const busy = useStore((s) => s.busy)
  const provider = useStore((s) => s.provider)
  return (
    <div className="flex h-full flex-col p-3">
      <div className="px-1 py-2">
        <Brand />
      </div>
      <Button
        variant="outline"
        size="sm"
        className="mt-2 w-full justify-start"
        onClick={() => {
          newChat()
          onNavigate?.()
        }}
        disabled={busy}
      >
        <Plus size={15} /> Yeni sohbet
      </Button>
      <div className="mt-4 mb-1 px-2 text-xs font-medium uppercase tracking-wide text-muted">Sohbetler</div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <ConversationList onNavigate={onNavigate} />
      </div>
      {provider && (
        <div className="mt-2 border-t border-border px-2 pt-2 text-[11px] text-muted">
          sağlayıcı: <span className="text-patina">{provider}</span>
        </div>
      )}
    </div>
  )
}

function ModelSelect() {
  const models = useStore((s) => s.models)
  const model = useStore((s) => s.model)
  const switchModel = useStore((s) => s.switchModel)
  const busy = useStore((s) => s.busy)
  const modelSwitching = useStore((s) => s.modelSwitching)
  if (!models.length) return null
  return (
    <div className="flex items-center gap-1.5">
      <Select
        value={model ?? undefined}
        onValueChange={switchModel}
        options={models}
        placeholder="Model"
        disabled={busy || modelSwitching}
        labelOf={shortModelName}
      />
      {modelSwitching && (
        <span className="flex items-center gap-1 text-[11px] text-muted">
          <Loader2 size={13} className="spin" /> yükleniyor…
        </span>
      )}
    </div>
  )
}

function ConnectionDot() {
  const connected = useStore((s) => s.connected)
  return (
    <span className="flex items-center gap-1.5 text-xs text-muted">
      <span className={cn('h-2 w-2 rounded-full', connected ? 'bg-patina pulse-ring' : 'bg-err')} />
      <span className="hidden sm:inline">{connected ? 'bağlı' : 'bağlanıyor…'}</span>
    </span>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
      <Brand size={44} className="flex-col gap-3" />
      <h1 className="mt-6 text-2xl font-semibold tracking-tight">Yerel ajanınla konuş</h1>
      <p className="mt-2 max-w-md text-sm text-muted">
        Hafif kodlama, derin araştırma ve gerçek dosya/sistem işleri — hepsi kendi makinende
        çalışan bir modelle.
      </p>
    </div>
  )
}

const SIDEBAR_MIN = 200
const SIDEBAR_MAX = 460
const SIDEBAR_DEFAULT = 256

function App() {
  useWebSocket()
  useAppData()
  const [navOpen, setNavOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('la-sidebar-collapsed') === '1')
  const toggleCollapsed = () =>
    setCollapsed((c) => {
      const next = !c
      localStorage.setItem('la-sidebar-collapsed', next ? '1' : '0')
      return next
    })
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const v = Number(localStorage.getItem('la-sidebar-w'))
    return v >= SIDEBAR_MIN && v <= SIDEBAR_MAX ? v : SIDEBAR_DEFAULT
  })
  const resizeSidebar = (x: number) => {
    const w = Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, Math.round(x)))
    setSidebarWidth(w)
    localStorage.setItem('la-sidebar-w', String(w))
  }
  const resetSidebar = () => {
    setSidebarWidth(SIDEBAR_DEFAULT)
    localStorage.setItem('la-sidebar-w', String(SIDEBAR_DEFAULT))
  }
  const hasMessages = useStore((s) => s.messages.length > 0)
  const artifactsOpen = useStore((s) => s.artifactsOpen)
  const hasArtifacts = useStore((s) => s.artifacts.length > 0)
  const showArtifacts = useStore((s) => s.showArtifacts)
  const closeArtifacts = useStore((s) => s.closeArtifacts)

  return (
    <>
      <AppShell
        sidebar={<Sidebar />}
        artifacts={<ArtifactPanel />}
        artifactsOpen={artifactsOpen}
        sidebarWidth={sidebarWidth}
        sidebarCollapsed={collapsed}
        onSidebarResize={resizeSidebar}
        onSidebarResetWidth={resetSidebar}
      >
        <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border px-3 sm:px-4">
          <Button variant="ghost" size="icon" className="md:hidden" onClick={() => setNavOpen(true)} aria-label="Menü">
            <Menu size={18} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="hidden md:inline-flex"
            onClick={toggleCollapsed}
            title={collapsed ? 'Kenar çubuğunu aç' : 'Kenar çubuğunu daralt'}
            aria-label="Kenar çubuğunu aç/kapat"
          >
            <PanelLeft size={17} />
          </Button>
          <div className="md:hidden">
            <Brand size={22} />
          </div>
          <div className="hidden md:block">
            <ModelSelect />
          </div>
          <div className="flex-1" />
          <ConnectionDot />
          {hasArtifacts && !artifactsOpen && (
            <Button variant="ghost" size="icon" onClick={showArtifacts} title="Artifact panelini aç" aria-label="Artifact panelini aç">
              <PanelRight size={17} />
            </Button>
          )}
          <Button variant="ghost" size="icon" onClick={() => setSettingsOpen(true)} title="Ayarlar" aria-label="Ayarlar">
            <Settings2 size={17} />
          </Button>
          <ThemeToggle />
        </header>

        {/* model select on mobile sits under the header */}
        <div className="border-b border-border px-3 py-2 md:hidden">
          <ModelSelect />
        </div>

        {hasMessages ? (
          <>
            <PlanStrip />
            <MessageList />
          </>
        ) : (
          <EmptyState />
        )}
        <Composer />
      </AppShell>

      {/* Mobile: sidebar drawer */}
      <div className="md:hidden">
        <Drawer open={navOpen} onClose={() => setNavOpen(false)} side="left" className="w-72">
          <Sidebar onNavigate={() => setNavOpen(false)} />
        </Drawer>
      </div>

      {/* Mobile/tablet: artifact panel as full overlay */}
      <div className="lg:hidden">
        <Drawer open={artifactsOpen} onClose={closeArtifacts} side="right" className="w-full max-w-[560px]">
          <ArtifactPanel />
        </Drawer>
      </div>

      <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
    </>
  )
}

export default App
