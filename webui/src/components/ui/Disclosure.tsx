import { useState, type ReactNode } from 'react'
import * as Collapsible from '@radix-ui/react-collapsible'
import { ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

interface DisclosureProps {
  icon?: ReactNode
  title: ReactNode
  meta?: ReactNode // right-aligned status/badge
  defaultOpen?: boolean
  accent?: 'accent' | 'patina' | 'muted'
  children: ReactNode
}

const accents: Record<NonNullable<DisclosureProps['accent']>, string> = {
  accent: 'border-l-accent',
  patina: 'border-l-patina',
  muted: 'border-l-border-strong',
}

export function Disclosure({
  icon,
  title,
  meta,
  defaultOpen = false,
  accent = 'muted',
  children,
}: DisclosureProps) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <Collapsible.Root
      open={open}
      onOpenChange={setOpen}
      className={cn('overflow-hidden rounded-lg border border-border border-l-2 bg-panel-2', accents[accent])}
    >
      <Collapsible.Trigger className="flex w-full items-center gap-2 px-3 py-2 text-left text-[13px] text-muted transition-colors hover:text-text">
        <ChevronRight size={14} className={cn('shrink-0 transition-transform', open && 'rotate-90')} />
        {icon}
        <span className="min-w-0 flex-1 truncate">{title}</span>
        {meta}
      </Collapsible.Trigger>
      <Collapsible.Content>
        <div className="border-t border-border/60 px-3 py-2.5 text-[13px]">{children}</div>
      </Collapsible.Content>
    </Collapsible.Root>
  )
}
