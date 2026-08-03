import { cn } from '@/lib/utils'

/** The "Copper & Patina" mark: a copper ring around a verdigris core. */
export function Brand({ className, size = 26 }: { className?: string; size?: number }) {
  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      <svg width={size} height={size} viewBox="0 0 100 100" aria-hidden>
        <defs>
          <linearGradient id="brand-copper" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="var(--accent-hover)" />
            <stop offset="1" stopColor="var(--accent)" />
          </linearGradient>
        </defs>
        <circle
          cx="50"
          cy="50"
          r="34"
          fill="none"
          stroke="url(#brand-copper)"
          strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray="150 60"
          transform="rotate(-40 50 50)"
        />
        <circle cx="50" cy="50" r="12" fill="var(--patina)" />
      </svg>
      <span className="text-[15px] font-semibold tracking-tight text-text">
        Local<span className="text-accent">Agent</span>
      </span>
    </div>
  )
}
