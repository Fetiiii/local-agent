import { AlertTriangle, Info, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { TimelineItem } from '@/lib/types'

type NoticeItem = Extract<TimelineItem, { kind: 'notice' }>

const styles = {
  info: { cls: 'text-muted', Icon: Info },
  warn: { cls: 'text-warn', Icon: AlertTriangle },
  error: { cls: 'text-err', Icon: XCircle },
}

export function NoticeLine({ item }: { item: NoticeItem }) {
  const { cls, Icon } = styles[item.level] ?? styles.info
  return (
    <div className={cn('flex items-center gap-2 text-[13px]', cls)}>
      <Icon size={14} className="shrink-0" />
      <span>{item.text}</span>
    </div>
  )
}
