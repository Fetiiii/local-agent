import * as Dialog from '@radix-ui/react-dialog'
import { RotateCcw, X } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { useStore } from '@/lib/store'
import type { LlmSettings } from '@/lib/types'

const DEFAULTS: LlmSettings = { temperature: 0.7, top_p: 1, max_tokens: 0, max_steps: 5 }

function Row({
  label,
  hint,
  children,
  value,
}: {
  label: string
  hint: string
  value: string
  children: React.ReactNode
}) {
  return (
    <div className="py-3.5">
      <div className="mb-1 flex items-baseline justify-between">
        <label className="text-[13.5px] font-medium text-text">{label}</label>
        <span className="font-mono text-[12px] text-accent">{value}</span>
      </div>
      {children}
      <p className="mt-1.5 text-[12px] text-muted">{hint}</p>
    </div>
  )
}

export function SettingsDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const settings = useStore((s) => s.settings)
  const update = useStore((s) => s.updateSettings)

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[92vw] max-w-md -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-2xl border border-border bg-panel shadow-[var(--shadow)] focus:outline-none">
          <div className="flex items-center gap-2 border-b border-border px-5 py-3.5">
            <Dialog.Title className="text-[15px] font-semibold text-text">Ayarlar</Dialog.Title>
            <span className="text-[12px] text-muted">· model üretim parametreleri</span>
            <div className="flex-1" />
            <Dialog.Close asChild>
              <Button variant="ghost" size="icon" aria-label="Kapat">
                <X size={17} />
              </Button>
            </Dialog.Close>
          </div>

          <div className="max-h-[70vh] overflow-y-auto px-5 py-2">
            <Row
              label="Temperature"
              value={settings.temperature.toFixed(2)}
              hint="Düşük = tutarlı/kararlı, yüksek = yaratıcı/çeşitli."
            >
              <input
                type="range"
                min={0}
                max={2}
                step={0.05}
                value={settings.temperature}
                onChange={(e) => update({ temperature: Number(e.target.value) })}
                className="w-full"
              />
            </Row>

            <div className="border-t border-border/60" />
            <Row
              label="Top-p"
              value={settings.top_p.toFixed(2)}
              hint="Çekirdek örnekleme eşiği. Genelde 1.0 bırakılır; temperature ile birlikte oynama."
            >
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={settings.top_p}
                onChange={(e) => update({ top_p: Number(e.target.value) })}
                className="w-full"
              />
            </Row>

            <div className="border-t border-border/60" />
            <Row
              label="Maks. yanıt uzunluğu"
              value={settings.max_tokens === 0 ? 'sınırsız' : `${settings.max_tokens} token`}
              hint="Tek yanıtta üretilecek maksimum token. 0 = sınırsız."
            >
              <input
                type="number"
                min={0}
                max={32768}
                step={128}
                value={settings.max_tokens}
                onChange={(e) => update({ max_tokens: Math.max(0, Number(e.target.value) || 0) })}
                className="w-full rounded-lg border border-border bg-panel-2 px-3 py-1.5 text-[13px] outline-none focus:border-accent"
              />
            </Row>

            <div className="border-t border-border/60" />
            <Row
              label="Maks. ajan adımı"
              value={`${settings.max_steps}`}
              hint="Ajanın bir soru için yapabileceği düşün→araç döngüsü sayısı (1–20)."
            >
              <input
                type="range"
                min={1}
                max={20}
                step={1}
                value={settings.max_steps}
                onChange={(e) => update({ max_steps: Number(e.target.value) })}
                className="w-full"
              />
            </Row>
          </div>

          <div className="flex items-center justify-between border-t border-border px-5 py-3">
            <Button variant="ghost" size="sm" onClick={() => update(DEFAULTS)}>
              <RotateCcw size={14} /> Varsayılana dön
            </Button>
            <Dialog.Close asChild>
              <Button size="sm">Tamam</Button>
            </Dialog.Close>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
