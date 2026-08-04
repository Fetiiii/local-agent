import {
  BarChart3,
  Code2,
  Eye,
  FileEdit,
  FilePlus2,
  FileText,
  Globe,
  Microscope,
  Search,
  Terminal,
  Users,
  Wrench,
  type LucideIcon,
} from 'lucide-react'

interface ToolMeta {
  label: string
  Icon: LucideIcon
}

const MAP: Record<string, ToolMeta> = {
  web_search: { label: 'Web araması', Icon: Search },
  web_scraper: { label: 'Web kazıma', Icon: Globe },
  deep_research: { label: 'Derin araştırma', Icon: Microscope },
  data_analyst: { label: 'Veri analisti', Icon: BarChart3 },
  image_analysis: { label: 'Görsel analizi', Icon: Eye },
  shell_executor: { label: 'Terminal', Icon: Terminal },
  file_reader: { label: 'Dosya okuma', Icon: FileText },
  file_architect: { label: 'Dosya oluşturma', Icon: FilePlus2 },
  file_surgeon: { label: 'Dosya düzenleme', Icon: FileEdit },
  final_answer: { label: 'Cevaptan', Icon: Code2 },
  delegate: { label: 'Delegasyon', Icon: Users },
}

export function toolMeta(name: string): ToolMeta {
  return MAP[name] ?? { label: name, Icon: Wrench }
}

/** Friendly Turkish label for a sub-agent id (coderAgent → "Kodlayıcı"). */
export function agentLabel(name: string): string {
  const n = (name || '').toLowerCase()
  if (n.includes('coder') || n.includes('code')) return 'Kodlayıcı'
  if (n.includes('research')) return 'Araştırmacı'
  if (n.includes('planner') || n.includes('plan')) return 'Planlayıcı'
  if (n.includes('writer') || n.includes('write')) return 'Yazar'
  if (n.includes('analyst') || n.includes('data')) return 'Analist'
  return name || 'Alt-ajan'
}
