import { useStore } from '@/lib/store'
import { useAutoScroll } from '@/hooks/useAutoScroll'
import { UserBubble } from './UserBubble'
import { AssistantTurn } from './AssistantTurn'

export function MessageList() {
  const messages = useStore((s) => s.messages)
  const { ref, onScroll } = useAutoScroll<HTMLDivElement>(messages)

  return (
    <div ref={ref} onScroll={onScroll} className="flex-1 overflow-y-auto">
      <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6">
        {messages.map((m) =>
          m.role === 'user' ? (
            <UserBubble key={m.id} text={m.text} />
          ) : (
            <AssistantTurn key={m.id} msg={m} />
          ),
        )}
      </div>
    </div>
  )
}
