import { useRef, useState } from 'react'
import { Loader2, Paperclip, SendHorizontal, Telescope } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/utils'
import { uploadFile } from '@/lib/api'
import { useStore } from '@/lib/store'

export function Composer() {
  const [text, setText] = useState('')
  const [upload, setUpload] = useState<{ msg: string; error?: boolean } | null>(null)
  const [uploading, setUploading] = useState(false)
  const taRef = useRef<HTMLTextAreaElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const busy = useStore((s) => s.busy)
  const connected = useStore((s) => s.connected)
  const sessionId = useStore((s) => s.sessionId)
  const deepSearch = useStore((s) => s.deepSearch)
  const setDeepSearch = useStore((s) => s.setDeepSearch)
  const submitPrompt = useStore((s) => s.submitPrompt)

  const grow = () => {
    const el = taRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }

  const submit = () => {
    if (!text.trim() || busy || !connected) return
    submitPrompt(text)
    setText('')
    requestAnimationFrame(() => {
      if (taRef.current) taRef.current.style.height = 'auto'
    })
  }

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file || !sessionId) return
    setUploading(true)
    setUpload({ msg: `${file.name} yükleniyor…` })
    try {
      const r = await uploadFile(sessionId, file)
      if (r.ok) {
        setUpload({
          msg: r.type === 'doc' ? `${r.name} eklendi · ${r.chunks} parça indekslendi` : `${r.name} eklendi (görsel)`,
        })
      } else {
        setUpload({ msg: `${r.name}: ${r.error || 'yükleme hatası'}`, error: true })
      }
    } catch {
      setUpload({ msg: 'Yükleme hatası', error: true })
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="mx-auto w-full max-w-3xl shrink-0 px-4 pb-5">
      {upload && (
        <div className={cn('mb-1.5 px-2 text-[12px]', upload.error ? 'text-err' : 'text-muted')}>{upload.msg}</div>
      )}
      <div className="flex flex-col gap-2 rounded-2xl border border-border bg-panel-2 p-2 shadow-[var(--shadow)] focus-within:border-border-strong">
        <textarea
          ref={taRef}
          rows={1}
          value={text}
          disabled={!connected}
          onChange={(e) => {
            setText(e.target.value)
            grow()
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              submit()
            }
          }}
          placeholder={connected ? 'Mesaj yaz…  (Enter gönder · Shift+Enter yeni satır)' : 'Bağlanıyor…'}
          className="max-h-52 min-h-[24px] w-full resize-none bg-transparent px-2 py-1.5 text-[14.5px] outline-none placeholder:text-muted"
        />
        <div className="flex items-center gap-2">
          <input ref={fileRef} type="file" className="hidden" onChange={onFile} />
          <Button
            variant="ghost"
            size="icon"
            onClick={() => fileRef.current?.click()}
            disabled={!sessionId || uploading}
            title="Dosya ekle (doküman → RAG, görsel → analiz)"
            aria-label="Dosya ekle"
          >
            {uploading ? <Loader2 size={17} className="spin" /> : <Paperclip size={17} />}
          </Button>
          <button
            type="button"
            onClick={() => setDeepSearch(!deepSearch)}
            title="Derin araştırma modu — yetenekli modeller için çok adımlı web araştırması"
            className={cn(
              'inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[12.5px] font-medium transition-colors',
              deepSearch ? 'border-patina/50 bg-patina-soft text-patina' : 'border-border text-muted hover:text-text',
            )}
          >
            <Telescope size={15} />
            DeepSearch
          </button>
          <div className="flex-1" />
          <Button size="icon" onClick={submit} disabled={!text.trim() || busy || !connected} aria-label="Gönder">
            <SendHorizontal size={17} />
          </Button>
        </div>
      </div>
    </div>
  )
}
