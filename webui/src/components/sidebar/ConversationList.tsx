import { MessageSquare, Trash2 } from 'lucide-react'
import { deleteConversation, fetchConversations } from '@/lib/api'
import { useStore } from '@/lib/store'
import { cn } from '@/lib/utils'

export function ConversationList({ onNavigate }: { onNavigate?: () => void }) {
  const conversations = useStore((s) => s.conversations)
  const threadId = useStore((s) => s.threadId)
  const busy = useStore((s) => s.busy)
  const resumeChat = useStore((s) => s.resumeChat)
  const setConversations = useStore((s) => s.setConversations)

  const remove = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    await deleteConversation(id)
    setConversations(await fetchConversations())
  }

  if (!conversations.length) {
    return <div className="px-2 py-3 text-[12.5px] text-muted">Henüz sohbet yok.</div>
  }

  return (
    <div className="space-y-0.5">
      {conversations.map((c) => (
        <div
          key={c.id}
          onClick={() => {
            if (busy) return
            resumeChat(c.id)
            onNavigate?.()
          }}
          className={cn(
            'group flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-[13px] transition-colors',
            c.id === threadId ? 'bg-accent-soft text-text' : 'text-muted hover:bg-panel-2 hover:text-text',
            busy && 'cursor-not-allowed opacity-60',
          )}
        >
          <MessageSquare size={14} className="shrink-0 opacity-70" />
          <span className="min-w-0 flex-1 truncate">{c.title || 'Adsız sohbet'}</span>
          <button
            onClick={(e) => remove(e, c.id)}
            title="Sil"
            className="shrink-0 opacity-0 transition-opacity hover:text-err group-hover:opacity-70"
          >
            <Trash2 size={14} />
          </button>
        </div>
      ))}
    </div>
  )
}
