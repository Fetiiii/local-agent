import { useEffect, useRef } from 'react'
import { createWebSocket, type WsClient } from '@/lib/ws'
import { useStore } from '@/lib/store'

/** Opens the WebSocket once on mount and wires it to the store. */
export function useWebSocket() {
  const ref = useRef<WsClient | null>(null)
  useEffect(() => {
    if (ref.current) return
    const client = createWebSocket({
      onEvent: (ev) => useStore.getState().applyEvent(ev),
      onStatus: (c) => useStore.getState().setConnected(c),
    })
    ref.current = client
    useStore.getState().setSend(client.send)
    return () => {
      client.close()
      ref.current = null
    }
  }, [])
}
