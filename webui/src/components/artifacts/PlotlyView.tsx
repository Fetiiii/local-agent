import { useEffect, useRef, useState } from 'react'
import { loadPlotly } from '@/lib/plotly'

function cssVar(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

export function PlotlyView({ json }: { json: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    let ro: ResizeObserver | null = null
    let cancelled = false

    loadPlotly()
      .then((Plotly) => {
        if (cancelled || !ref.current) return
        let fig: { data?: unknown[]; layout?: Record<string, unknown> }
        try {
          fig = JSON.parse(json)
        } catch {
          setError('Grafik verisi okunamadı')
          return
        }
        const text = cssVar('--text')
        const border = cssVar('--border')
        const layout = {
          ...(fig.layout ?? {}),
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(0,0,0,0)',
          font: { color: text, family: 'Inter, sans-serif', ...(fig.layout?.font as object) },
          xaxis: { gridcolor: border, zerolinecolor: border, ...(fig.layout?.xaxis as object) },
          yaxis: { gridcolor: border, zerolinecolor: border, ...(fig.layout?.yaxis as object) },
          margin: { t: 40, r: 16, b: 40, l: 48, ...(fig.layout?.margin as object) },
        }
        Plotly.newPlot(ref.current, fig.data ?? [], layout, {
          responsive: true,
          displmodeBar: false,
        })
        ro = new ResizeObserver(() => ref.current && Plotly.Plots.resize(ref.current))
        ro.observe(ref.current)
      })
      .catch((e) => setError(String(e?.message ?? e)))

    return () => {
      cancelled = true
      ro?.disconnect()
      if (window.Plotly && el) window.Plotly.purge(el)
    }
  }, [json])

  if (error) return <div className="p-4 text-sm text-err">{error}</div>
  return <div ref={ref} className="h-[380px] w-full" />
}
