import { useEffect } from 'react'
import { fetchConversations, fetchModels, fetchSettings } from '@/lib/api'
import { hasUserSettings, useStore } from '@/lib/store'

/** Loads models + settings + conversation list on mount, refreshes the list when
 *  a turn finishes, and syncs settings to the server on (re)connect. */
export function useAppData() {
  useEffect(() => {
    const { setModels, setConversations, initSettings } = useStore.getState()
    const reload = () => fetchConversations().then(setConversations).catch(() => {})

    fetchModels()
      .then((r) => setModels(r.provider, r.models))
      .catch(() => {})
    // Show the server's real generation defaults unless the user has their own.
    if (!hasUserSettings()) fetchSettings().then(initSettings).catch(() => {})
    reload()

    const unsub = useStore.subscribe((state, prev) => {
      if (prev.busy && !state.busy) {
        reload()
        if (state.threadId && state.messages.length) {
          state.send({ type: 'persist', ui: { messages: state.messages, artifacts: state.artifacts } })
        }
      }
      // On (re)connect, re-apply the user's settings so a reconnected socket keeps them.
      if (!prev.connected && state.connected && hasUserSettings()) {
        state.pushSettings()
      }
    })
    return unsub
  }, [])
}
