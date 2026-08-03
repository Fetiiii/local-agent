import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

type Variant = 'primary' | 'ghost' | 'outline' | 'danger' | 'patina'
type Size = 'sm' | 'md' | 'icon'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
}

const variants: Record<Variant, string> = {
  primary:
    'bg-accent text-accent-contrast hover:bg-accent-hover shadow-[0_1px_0_rgba(255,255,255,0.12)_inset]',
  patina: 'bg-patina text-accent-contrast hover:brightness-110',
  ghost: 'text-muted hover:text-text hover:bg-panel-2',
  outline: 'border border-border text-text hover:border-border-strong hover:bg-panel-2',
  danger: 'bg-err text-white hover:brightness-110',
}

const sizes: Record<Size, string> = {
  sm: 'h-8 px-3 text-[13px] gap-1.5 rounded-lg',
  md: 'h-10 px-4 text-sm gap-2 rounded-xl',
  icon: 'h-9 w-9 rounded-lg',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        'inline-flex items-center justify-center font-medium select-none',
        'transition-colors duration-150 outline-none',
        'focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:ring-offset-0',
        'disabled:opacity-50 disabled:pointer-events-none',
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  ),
)
Button.displayName = 'Button'
