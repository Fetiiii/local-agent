import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface AppShellProps {
  sidebar: ReactNode
  children: ReactNode
  artifacts?: ReactNode
  artifactsOpen?: boolean
  sidebarWidth?: number
  sidebarCollapsed?: boolean
  onSidebarResize?: (clientX: number) => void
  onSidebarResetWidth?: () => void
}

/** Draggable divider on the sidebar's right edge. Since the sidebar is the
 *  left-most column, the pointer's clientX equals the desired width. */
function ResizeHandle({
  onResize,
  onReset,
}: {
  onResize: (x: number) => void
  onReset?: () => void
}) {
  const onDown = (e: React.PointerEvent) => {
    e.preventDefault()
    document.body.style.userSelect = 'none'
    document.body.style.cursor = 'col-resize'
    const move = (ev: PointerEvent) => onResize(ev.clientX)
    const up = () => {
      document.body.style.userSelect = ''
      document.body.style.cursor = ''
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }
  return (
    <div
      onPointerDown={onDown}
      onDoubleClick={onReset}
      title="Sürükle: genişliği ayarla · Çift tık: sıfırla"
      className="group absolute right-0 top-0 z-10 h-full w-1.5 translate-x-1/2 cursor-col-resize"
    >
      <div className="mx-auto h-full w-px bg-transparent transition-colors group-hover:bg-accent/50" />
    </div>
  )
}

/** Three-column shell: conversations | chat | artifacts.
 *  The artifact rail slides in only when there is something to show. */
export function AppShell({
  sidebar,
  children,
  artifacts,
  artifactsOpen,
  sidebarWidth = 256,
  sidebarCollapsed = false,
  onSidebarResize,
  onSidebarResetWidth,
}: AppShellProps) {
  return (
    <div className="flex h-full w-full overflow-hidden bg-bg text-text">
      <aside
        style={{ width: sidebarCollapsed ? 0 : sidebarWidth }}
        className={cn(
          'relative hidden shrink-0 flex-col border-r border-border bg-panel transition-[width] duration-200 md:flex',
          sidebarCollapsed && 'overflow-hidden border-r-0',
        )}
      >
        {sidebar}
        {onSidebarResize && !sidebarCollapsed && (
          <ResizeHandle onResize={onSidebarResize} onReset={onSidebarResetWidth} />
        )}
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">{children}</main>

      <aside
        className={cn(
          'hidden shrink-0 border-l border-border bg-panel transition-[width] duration-300 ease-out lg:block',
          artifactsOpen ? 'w-[440px] xl:w-[520px]' : 'w-0 overflow-hidden border-l-0',
        )}
      >
        {artifacts}
      </aside>
    </div>
  )
}
