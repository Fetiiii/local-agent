import { useEffect, useRef } from 'react'

/** Keeps a scroll container pinned to the bottom while new content streams in,
 *  unless the user has scrolled up to read earlier messages. */
export function useAutoScroll<T extends HTMLElement>(dep: unknown) {
  const ref = useRef<T>(null)
  const stick = useRef(true)

  const onScroll = () => {
    const el = ref.current
    if (!el) return
    stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  }

  useEffect(() => {
    const el = ref.current
    if (el && stick.current) el.scrollTop = el.scrollHeight
  }, [dep])

  return { ref, onScroll }
}
