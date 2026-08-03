import { useState } from 'react'
import { Check, Copy } from 'lucide-react'

export function SourceCode({ code, lang }: { code: string; lang?: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1400)
    } catch {
      /* clipboard unavailable */
    }
  }
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-code-bg">
      <div className="flex items-center justify-between border-b border-border/70 px-3 py-1.5">
        <span className="font-mono text-[11px] uppercase tracking-wide text-muted">{lang || 'kaynak'}</span>
        <button onClick={copy} className="flex items-center gap-1 text-[11px] text-muted transition-colors hover:text-accent">
          {copied ? <Check size={13} /> : <Copy size={13} />}
          {copied ? 'kopyalandı' : 'kopyala'}
        </button>
      </div>
      <pre className="max-h-[70vh] overflow-auto p-3 font-mono text-[12.5px] leading-relaxed">
        <code>{code}</code>
      </pre>
    </div>
  )
}
