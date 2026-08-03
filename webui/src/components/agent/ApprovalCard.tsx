import { Check, ShieldAlert, X } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Markdown } from '@/lib/markdown'
import { useStore } from '@/lib/store'
import type { TimelineItem } from '@/lib/types'

type ApprovalItem = Extract<TimelineItem, { kind: 'approval' }>

export function ApprovalCard({ item }: { item: ApprovalItem }) {
  const respond = useStore((s) => s.respondApproval)
  const pending = item.status === 'pending'

  return (
    <div className="overflow-hidden rounded-xl border border-warn/60 bg-warn/5">
      <div className="flex items-center gap-2 border-b border-warn/30 px-3.5 py-2.5">
        <ShieldAlert size={16} className="text-warn" />
        <span className="text-[13.5px] font-semibold text-text">{item.title}</span>
        {!pending && (
          <span
            className={`ml-auto rounded-full px-2 py-0.5 text-[11px] font-medium ${
              item.status === 'approved' ? 'bg-patina/15 text-patina' : 'bg-err/15 text-err'
            }`}
          >
            {item.status === 'approved' ? 'onaylandı' : 'reddedildi'}
          </span>
        )}
      </div>
      <div className="px-3.5 py-3 text-[13.5px]">
        <Markdown>{item.detail}</Markdown>
      </div>
      {pending && (
        <div className="flex gap-2 border-t border-warn/20 px-3.5 py-2.5">
          <Button variant="patina" size="sm" onClick={() => respond(item.id, true)}>
            <Check size={15} /> Onayla
          </Button>
          <Button variant="danger" size="sm" onClick={() => respond(item.id, false)}>
            <X size={15} /> Reddet
          </Button>
        </div>
      )}
    </div>
  )
}
