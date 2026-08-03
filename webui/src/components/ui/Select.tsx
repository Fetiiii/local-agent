import * as RSelect from '@radix-ui/react-select'
import { Check, ChevronDown } from 'lucide-react'

interface SelectProps {
  value: string | undefined
  onValueChange: (v: string) => void
  options: string[]
  placeholder?: string
  disabled?: boolean
  labelOf?: (value: string) => string
}

export function Select({ value, onValueChange, options, placeholder, disabled, labelOf }: SelectProps) {
  const label = (v: string) => (labelOf ? labelOf(v) : v)
  return (
    <RSelect.Root value={value} onValueChange={onValueChange} disabled={disabled}>
      <RSelect.Trigger
        title={value}
        className="inline-flex h-8 max-w-[200px] items-center gap-1.5 rounded-lg border border-border bg-panel-2 px-2.5 text-[13px] text-text outline-none transition-colors hover:border-border-strong focus-visible:ring-2 focus-visible:ring-accent/60 disabled:opacity-50"
        aria-label="Model"
      >
        <span className="truncate">{value ? label(value) : placeholder}</span>
        <RSelect.Icon className="ml-auto shrink-0">
          <ChevronDown size={14} className="text-muted" />
        </RSelect.Icon>
      </RSelect.Trigger>
      <RSelect.Portal>
        <RSelect.Content
          position="popper"
          sideOffset={6}
          className="z-50 max-h-72 overflow-hidden rounded-xl border border-border bg-panel shadow-[var(--shadow)]"
        >
          <RSelect.Viewport className="p-1">
            {options.map((opt) => (
              <RSelect.Item
                key={opt}
                value={opt}
                title={opt}
                className="flex max-w-[360px] cursor-pointer items-center gap-2 rounded-lg px-2.5 py-1.5 text-[13px] text-text outline-none data-[highlighted]:bg-accent-soft data-[highlighted]:text-accent"
              >
                <RSelect.ItemText>{label(opt)}</RSelect.ItemText>
                <RSelect.ItemIndicator className="ml-auto">
                  <Check size={14} className="text-accent" />
                </RSelect.ItemIndicator>
              </RSelect.Item>
            ))}
          </RSelect.Viewport>
        </RSelect.Content>
      </RSelect.Portal>
    </RSelect.Root>
  )
}
