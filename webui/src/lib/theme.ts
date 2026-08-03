// Theme is applied via `data-theme` on <html>. Dark is the default; the choice
// is persisted in localStorage so it survives reloads.
export type Theme = 'dark' | 'light'

const KEY = 'local-agent-theme'

export function getStoredTheme(): Theme {
  const v = localStorage.getItem(KEY)
  return v === 'light' ? 'light' : 'dark'
}

export function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme
  localStorage.setItem(KEY, theme)
}

export function initTheme(): Theme {
  const t = getStoredTheme()
  applyTheme(t)
  return t
}
