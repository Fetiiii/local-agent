import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface DrawerProps {
  open: boolean
  onClose: () => void
  side?: 'left' | 'right'
  children: ReactNode
  className?: string
}

/** Mobile off-canvas panel with a backdrop. Desktop uses the fixed columns. */
export function Drawer({ open, onClose, side = 'left', children, className }: DrawerProps) {
  return (
    <div className={cn('fixed inset-0 z-40', open ? '' : 'pointer-events-none')}>
      <div
        onClick={onClose}
        className={cn('absolute inset-0 bg-black/50 transition-opacity', open ? 'opacity-100' : 'opacity-0')}
      />
      <div
        className={cn(
          'absolute top-0 bottom-0 bg-panel shadow-[var(--shadow)] transition-transform duration-300 ease-out',
          side === 'left' ? 'left-0 border-r border-border' : 'right-0 border-l border-border',
          open ? 'translate-x-0' : side === 'left' ? '-translate-x-full' : 'translate-x-full',
          className,
        )}
      >
        {children}
      </div>
    </div>
  )
}
