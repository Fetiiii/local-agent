import * as RTabs from '@radix-ui/react-tabs'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function Tabs({
  defaultValue,
  children,
  className,
}: {
  defaultValue: string
  children: ReactNode
  className?: string
}) {
  return (
    <RTabs.Root defaultValue={defaultValue} className={cn('flex flex-col', className)}>
      {children}
    </RTabs.Root>
  )
}

export function TabsList({ children }: { children: ReactNode }) {
  return (
    <RTabs.List className="flex gap-1 rounded-lg border border-border bg-panel-2 p-0.5">
      {children}
    </RTabs.List>
  )
}

export function TabsTrigger({ value, children }: { value: string; children: ReactNode }) {
  return (
    <RTabs.Trigger
      value={value}
      className={cn(
        'flex-1 rounded-md px-3 py-1.5 text-[13px] font-medium text-muted transition-colors',
        'hover:text-text data-[state=active]:bg-accent data-[state=active]:text-accent-contrast',
      )}
    >
      {children}
    </RTabs.Trigger>
  )
}

export function TabsContent({ value, children, className }: { value: string; children: ReactNode; className?: string }) {
  return (
    <RTabs.Content value={value} className={cn('mt-3 focus-visible:outline-none', className)}>
      {children}
    </RTabs.Content>
  )
}
