import type { ClientMessage, ServerEvent } from './types'

interface WsHandlers {
  onEvent: (ev: ServerEvent) => void
  onStatus: (connected: boolean) => void
}

export interface WsClient {
  send: (msg: ClientMessage) => void
  close: () => void
}

/** Persistent WebSocket to /ws with auto-reconnect. Survives long-running turns
 *  and mid-turn approval round-trips (the agent runs in a background task). */
export function createWebSocket({ onEvent, onStatus }: WsHandlers): WsClient {
  let ws: WebSocket | null = null
  let closedByUser = false
  let retry: ReturnType<typeof setTimeout> | null = null

  const url = () => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    return `${proto}://${location.host}/ws`
  }

  const connect = () => {
    ws = new WebSocket(url())
    ws.onopen = () => onStatus(true)
    ws.onclose = () => {
      onStatus(false)
      if (!closedByUser) retry = setTimeout(connect, 1500)
    }
    ws.onerror = () => ws?.close()
    ws.onmessage = (e) => {
      try {
        onEvent(JSON.parse(e.data) as ServerEvent)
      } catch {
        /* ignore malformed frames */
      }
    }
  }

  connect()

  return {
    send: (msg) => {
      if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg))
    },
    close: () => {
      closedByUser = true
      if (retry) clearTimeout(retry)
      ws?.close()
    },
  }
}
