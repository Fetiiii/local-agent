import { Markdown } from '@/lib/markdown'
import type { ChatMessage } from '@/lib/types'
import { Timeline } from '@/components/agent/Timeline'
import { TypingIndicator } from './TypingIndicator'

function Avatar() {
  return (
    <svg width={26} height={26} viewBox="0 0 100 100" className="mt-0.5 shrink-0" aria-hidden>
      <circle cx="50" cy="50" r="46" fill="var(--panel-2)" stroke="var(--border)" />
      <circle
        cx="50"
        cy="50"
        r="26"
        fill="none"
        stroke="var(--accent)"
        strokeWidth="7"
        strokeLinecap="round"
        strokeDasharray="115 45"
        transform="rotate(-40 50 50)"
      />
      <circle cx="50" cy="50" r="9" fill="var(--patina)" />
    </svg>
  )
}

export function AssistantTurn({ msg }: { msg: ChatMessage }) {
  const empty = !msg.text && !msg.timeline.length && !msg.plan.length
  return (
    <div className="flex gap-3">
      <Avatar />
      <div className="min-w-0 flex-1 space-y-3 pt-0.5">
        <Timeline items={msg.timeline} turnDone={msg.done} />
        {msg.text && <Markdown>{msg.text}</Markdown>}
        {msg.pending && empty && <TypingIndicator />}
      </div>
    </div>
  )
}
