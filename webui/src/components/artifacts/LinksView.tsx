import { ExternalLink } from 'lucide-react'
import type { LinkItem } from '@/lib/types'

function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

export function LinksView({ items }: { items: LinkItem[] }) {
  return (
    <ul className="space-y-2">
      {items.map((it, i) => (
        <li key={i} className="rounded-lg border border-border bg-panel-2 p-3 transition-colors hover:border-border-strong">
          <a href={it.link} target="_blank" rel="noopener noreferrer" className="group block">
            <div className="flex items-start gap-2">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded bg-accent-soft text-[11px] font-medium text-accent">
                {i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5 text-[14px] font-medium text-text group-hover:text-accent">
                  <span className="truncate">{it.title || hostname(it.link)}</span>
                  <ExternalLink size={13} className="shrink-0 text-muted" />
                </div>
                <div className="truncate text-[12px] text-patina">{hostname(it.link)}</div>
                {it.snippet && <p className="mt-1 line-clamp-3 text-[12.5px] text-muted">{it.snippet}</p>}
              </div>
            </div>
          </a>
        </li>
      ))}
    </ul>
  )
}
