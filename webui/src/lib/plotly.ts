// Lazy-load the plotly.js bundle that the backend vendors at /static/vendor/
// (version-matched to the figure JSON it produces). Loaded once, on demand, so
// it never bloats the main app bundle and stays fully offline.
interface PlotlyLike {
  newPlot: (el: HTMLElement, data: unknown[], layout: unknown, config: unknown) => void
  Plots: { resize: (el: HTMLElement) => void }
  purge: (el: HTMLElement) => void
}

declare global {
  interface Window {
    Plotly?: PlotlyLike
  }
}

let promise: Promise<PlotlyLike> | null = null

export function loadPlotly(): Promise<PlotlyLike> {
  if (window.Plotly) return Promise.resolve(window.Plotly)
  if (promise) return promise
  promise = new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = '/static/vendor/plotly.min.js'
    s.async = true
    s.onload = () => (window.Plotly ? resolve(window.Plotly) : reject(new Error('Plotly yüklenemedi')))
    s.onerror = () => reject(new Error('plotly.min.js getirilemedi'))
    document.head.appendChild(s)
  })
  return promise
}
