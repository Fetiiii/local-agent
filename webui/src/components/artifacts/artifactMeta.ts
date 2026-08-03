import { Code2, FileText, Image, Link2, LineChart, Table, type LucideIcon } from 'lucide-react'
import type { Artifact } from '@/lib/types'

export function artifactMeta(a: Artifact): { label: string; Icon: LucideIcon } {
  switch (a.type) {
    case 'image':
      return { label: 'Görsel', Icon: Image }
    case 'plotly':
      return { label: 'Grafik', Icon: LineChart }
    case 'table':
      return { label: 'Tablo', Icon: Table }
    case 'links':
      return { label: `Kaynaklar (${a.items.length})`, Icon: Link2 }
    case 'text':
      return { label: 'Metin', Icon: FileText }
    case 'file': {
      if (a.kind === 'html') return { label: a.name || 'HTML', Icon: Code2 }
      if (a.kind === 'csv' || a.kind === 'excel') return { label: a.name || 'Tablo', Icon: Table }
      return { label: a.name || 'Dosya', Icon: FileText }
    }
  }
}
