import { sanitizeHtml } from '@/lib/sanitize'

export function TableView({ html }: { html: string }) {
  return (
    <div
      className="artifact-table overflow-x-auto"
      dangerouslySetInnerHTML={{ __html: sanitizeHtml(html) }}
    />
  )
}
