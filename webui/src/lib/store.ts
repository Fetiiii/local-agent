import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'
import type {
  Artifact,
  ChatMessage,
  ClientMessage,
  ConversationMeta,
  LlmSettings,
  PlanItem,
  ServerEvent,
  TimelineItem,
} from './types'
import { fetchModels, switchModel as apiSwitchModel } from './api'

const DEFAULT_SETTINGS: LlmSettings = { temperature: 0.7, top_p: 1, max_tokens: 0, max_steps: 5 }
const SETTINGS_KEY = 'la-settings'

export function hasUserSettings(): boolean {
  return localStorage.getItem(SETTINGS_KEY) !== null
}

function loadSettings(): LlmSettings {
  try {
    const v = localStorage.getItem(SETTINGS_KEY)
    if (v) return { ...DEFAULT_SETTINGS, ...JSON.parse(v) }
  } catch {
    /* ignore */
  }
  return DEFAULT_SETTINGS
}

const uid = () => (crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2))

function emptyAssistant(): ChatMessage {
  return {
    id: uid(),
    role: 'assistant',
    text: '',
    timeline: [],
    plan: [],
    pending: true,
    streaming: false,
    done: false,
  }
}

/** Detect substantial HTML documents in a final answer's code fences so they can
 *  be surfaced in the artifact panel (Code | Preview), Claude-artifacts style. */
function extractHtmlArtifacts(text: string): string[] {
  const out: string[] = []
  const fence = /```(?:html|htm)?\s*\n([\s\S]*?)```/gi
  let m: RegExpExecArray | null
  while ((m = fence.exec(text))) {
    const code = m[1].trim()
    if (code.length > 120 && /<!doctype html|<html[\s>]|<body[\s>]/i.test(code)) out.push(code)
  }
  return out
}

/** Living-plan heuristic: `step.plan` is regenerated each step with no stable ids,
 *  so we keep first-seen order and tick items off once they drop out of the plan. */
function mergePlan(existing: PlanItem[], next: string[]): PlanItem[] {
  const merged = existing.map((p) => (next.includes(p.text) ? p : { ...p, done: true }))
  for (const text of next) {
    if (!merged.some((p) => p.text === text)) merged.push({ text, done: false })
  }
  return merged
}

interface AppState {
  // connection / session
  connected: boolean
  sessionId: string | null
  threadId: string | null
  busy: boolean

  // chat
  messages: ChatMessage[]
  currentAssistantId: string | null

  // artifacts
  artifacts: { id: string; sourceTool: string; artifact: Artifact }[]
  activeArtifactId: string | null
  artifactsOpen: boolean

  // controls (wired further in Faz 4)
  models: string[]
  provider: string
  model: string | null
  deepSearch: boolean
  orchestrate: boolean
  modelSwitching: boolean
  conversations: ConversationMeta[]
  settings: LlmSettings

  // transport hookup
  send: (msg: ClientMessage) => void

  // actions
  setConnected: (v: boolean) => void
  setSend: (fn: (msg: ClientMessage) => void) => void
  applyEvent: (ev: ServerEvent) => void
  submitPrompt: (text: string) => void
  respondApproval: (id: string, approved: boolean) => void
  newChat: () => void
  resumeChat: (id: string) => void
  setModel: (m: string) => void
  setModels: (provider: string, models: string[], current?: string) => void
  switchModel: (m: string) => void
  setDeepSearch: (v: boolean) => void
  setOrchestrate: (v: boolean) => void
  setConversations: (list: ConversationMeta[]) => void
  openArtifact: (id: string) => void
  closeArtifacts: () => void
  showArtifacts: () => void
  initSettings: (s: Partial<LlmSettings>) => void // from backend defaults (display only)
  updateSettings: (partial: Partial<LlmSettings>) => void // user change → persist + send
  pushSettings: () => void // send current settings to server (on connect if user-set)
}

export const useStore = create<AppState>()(
  immer((set, get) => ({
    connected: false,
    sessionId: null,
    threadId: null,
    busy: false,
    messages: [],
    currentAssistantId: null,
    artifacts: [],
    activeArtifactId: null,
    artifactsOpen: false,
    models: [],
    provider: '',
    model: null,
    deepSearch: false,
    orchestrate: false,
    modelSwitching: false,
    conversations: [],
    settings: loadSettings(),
    send: () => {},

    setConnected: (v) => set((s) => void (s.connected = v)),
    setSend: (fn) => set((s) => void (s.send = fn)),
    setModel: (m) => set((s) => void (s.model = m)),
    setModels: (provider, models, current) =>
      set((s) => {
        s.provider = provider
        s.models = models
        if (current && models.includes(current)) s.model = current
        else if (!s.model || !models.includes(s.model)) s.model = models[0] ?? null
      }),
    switchModel: (m) => {
      if (get().modelSwitching || get().busy || m === get().model) return
      set((s) => void (s.modelSwitching = true))
      apiSwitchModel(m)
        .then((res) => {
          if (res.ok) {
            set((s) => void (s.model = res.model ?? m))
          } else {
            set((s) => {
              const msg = emptyAssistant()
              msg.pending = false
              msg.done = true
              msg.timeline.push({
                kind: 'notice',
                id: uid(),
                text: `Model değiştirilemedi: ${res.error ?? 'bilinmeyen hata'}`,
                level: 'error',
              })
              s.messages.push(msg)
            })
          }
        })
        .catch(() => {})
        .finally(() => {
          set((s) => void (s.modelSwitching = false))
          fetchModels()
            .then((r) => get().setModels(r.provider, r.models, r.current))
            .catch(() => {})
        })
    },
    setDeepSearch: (v) => set((s) => void (s.deepSearch = v)),
    setOrchestrate: (v) => set((s) => void (s.orchestrate = v)),
    setConversations: (list) => set((s) => void (s.conversations = list)),
    openArtifact: (id) =>
      set((s) => {
        s.activeArtifactId = id
        s.artifactsOpen = true
      }),
    closeArtifacts: () => set((s) => void (s.artifactsOpen = false)),
    showArtifacts: () => set((s) => void (s.artifactsOpen = s.artifacts.length > 0)),
    initSettings: (s) => set((st) => void (st.settings = { ...st.settings, ...s })),
    updateSettings: (partial) => {
      set((st) => void (st.settings = { ...st.settings, ...partial }))
      const next = get().settings
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(next))
      get().send({ type: 'settings', settings: next })
    },
    pushSettings: () => get().send({ type: 'settings', settings: get().settings }),

    applyEvent: (ev) =>
      set((s) => {
        const cur = (): ChatMessage | undefined =>
          s.messages.find((m) => m.id === s.currentAssistantId)

        switch (ev.type) {
          case 'session':
            s.sessionId = ev.id
            s.threadId = ev.thread_id
            // A 'session' arriving while busy means the socket dropped mid-turn and
            // auto-reconnected; the turn's 'done' went to the dead socket, so the
            // input would stay locked forever. Release it and close the dangling
            // assistant turn with a notice.
            if (s.busy) {
              const a = s.messages.find((m) => m.id === s.currentAssistantId)
              if (a) {
                a.pending = false
                a.streaming = false
                a.done = true
                a.timeline.push({
                  kind: 'notice',
                  id: uid(),
                  text: 'Bağlantı koptu ve yeniden kuruldu — yanıt yarıda kalmış olabilir, tekrar deneyebilirsin.',
                  level: 'warn',
                })
              }
              s.currentAssistantId = null
              s.busy = false
            }
            break

          case 'thread':
            s.threadId = ev.id
            s.messages = []
            s.artifacts = []
            s.activeArtifactId = null
            s.artifactsOpen = false
            s.currentAssistantId = null
            s.busy = false
            break

          case 'history': {
            s.threadId = ev.thread_id
            s.artifacts = []
            s.activeArtifactId = null
            s.artifactsOpen = false
            s.currentAssistantId = null
            s.busy = false
            // Rich state (full timeline + artifacts) if it was persisted; else
            // fall back to rebuilding plain bubbles from the message history.
            if (ev.ui && Array.isArray(ev.ui.messages) && ev.ui.messages.length) {
              s.messages = ev.ui.messages.map((m) => ({
                ...m,
                pending: false,
                streaming: false,
                done: true,
                timeline: (m.timeline || []).map((t) =>
                  t.kind === 'step' ? { ...t, streaming: false } : t,
                ),
              }))
              s.artifacts = ev.ui.artifacts || []
              break
            }
            s.messages = ev.messages.map((m) =>
              m.role === 'user'
                ? {
                    id: uid(),
                    role: 'user',
                    text: m.content,
                    timeline: [],
                    plan: [],
                    pending: false,
                    streaming: false,
                    done: true,
                  }
                : {
                    id: uid(),
                    role: 'assistant',
                    text: m.content,
                    timeline: [],
                    plan: [],
                    pending: false,
                    streaming: false,
                    done: true,
                  },
            )
            break
          }

          case 'step': {
            const a = cur()
            if (!a) break
            a.pending = false
            if (ev.thought)
              a.timeline.push({ kind: 'step', id: uid(), thought: ev.thought, streaming: false })
            if (ev.plan && ev.plan.length) a.plan = mergePlan(a.plan, ev.plan)
            break
          }

          case 'thinking': {
            const a = cur()
            if (!a) break
            a.pending = false
            const live = a.timeline.find(
              (t): t is Extract<TimelineItem, { kind: 'step' }> => t.kind === 'step' && !!t.streaming,
            )
            if (ev.reset) {
              if (live) a.timeline = a.timeline.filter((t) => t !== live)
            } else if (ev.done) {
              if (live) live.streaming = false
            } else if (ev.text) {
              if (live) live.thought += ev.text
              else a.timeline.push({ kind: 'step', id: uid(), thought: ev.text, streaming: true })
            }
            break
          }

          case 'plan': {
            const a = cur()
            if (!a) break
            a.pending = false
            a.plan = mergePlan(a.plan, ev.plan)
            break
          }

          case 'tool_start': {
            const a = cur()
            if (!a) break
            a.pending = false
            if (ev.name === 'shell_executor') {
              a.timeline.push({
                kind: 'terminal',
                id: ev.id,
                command: String((ev.args as any)?.command ?? ''),
                cwd: (ev.args as any)?.cwd ? String((ev.args as any).cwd) : undefined,
                status: 'running',
                artifactIds: [],
              })
            } else {
              a.timeline.push({
                kind: 'tool',
                id: ev.id,
                name: ev.name,
                args: ev.args,
                status: 'running',
                artifactIds: [],
              })
            }
            break
          }

          case 'tool_end': {
            const a = cur()
            if (!a) break
            const item = a.timeline.find(
              (t): t is Extract<TimelineItem, { kind: 'tool' | 'terminal' }> =>
                (t.kind === 'tool' || t.kind === 'terminal') && t.id === ev.id,
            )
            const artifactIds: string[] = []
            for (const art of ev.artifacts ?? []) {
              const id = uid()
              s.artifacts.push({ id, sourceTool: ev.name, artifact: art })
              artifactIds.push(id)
            }
            if (item) {
              item.status = 'done'
              if (item.kind === 'terminal') item.output = ev.result
              else item.result = ev.result
              item.artifactIds.push(...artifactIds)
            }
            if (artifactIds.length) {
              s.artifactsOpen = true
              s.activeArtifactId = artifactIds[artifactIds.length - 1]
            }
            break
          }

          case 'token': {
            const a = cur()
            if (!a) break
            a.pending = false
            a.streaming = true
            a.text += ev.text
            break
          }

          case 'final': {
            const a = cur()
            if (!a) break
            a.pending = false
            a.text = ev.text
            a.plan = a.plan.map((p) => ({ ...p, done: true }))
            // Surface any full HTML documents in the answer as artifacts.
            for (const html of extractHtmlArtifacts(ev.text)) {
              const id = uid()
              s.artifacts.push({
                id,
                sourceTool: 'final_answer',
                artifact: { type: 'file', path: 'onizleme.html', name: 'onizleme.html', kind: 'html', text: html },
              })
              s.activeArtifactId = id
              s.artifactsOpen = true
            }
            break
          }

          case 'notice': {
            const a = cur()
            const item = {
              kind: 'notice' as const,
              id: uid(),
              text: ev.text,
              level: (ev.level ?? 'info') as 'info' | 'warn' | 'error',
            }
            if (a) a.timeline.push(item)
            else {
              const m = emptyAssistant()
              m.pending = false
              m.done = true
              m.timeline.push(item)
              s.messages.push(m)
            }
            break
          }

          case 'approval_request': {
            const a = cur()
            if (!a) break
            a.pending = false
            a.timeline.push({
              kind: 'approval',
              id: ev.id,
              title: ev.title,
              detail: ev.detail,
              status: 'pending',
            })
            break
          }

          case 'done': {
            const a = cur()
            if (a) {
              a.streaming = false
              a.done = true
            }
            s.busy = false
            s.currentAssistantId = null
            break
          }
        }
      }),

    submitPrompt: (text) => {
      const t = text.trim()
      if (!t || get().busy || !get().connected || get().modelSwitching) return
      const assistant = emptyAssistant()
      set((s) => {
        s.messages.push({
          id: uid(),
          role: 'user',
          text: t,
          timeline: [],
          plan: [],
          pending: false,
          streaming: false,
          done: true,
        })
        s.messages.push(assistant)
        s.currentAssistantId = assistant.id
        s.busy = true
      })
      const { model, deepSearch, orchestrate } = get()
      get().send({
        type: 'user_message',
        content: t,
        model: model ?? undefined,
        deep_research: deepSearch,
        orchestrate,
      })
    },

    respondApproval: (id, approved) => {
      set((s) => {
        for (const m of s.messages) {
          const item = m.timeline.find((t) => t.kind === 'approval' && t.id === id)
          if (item && item.kind === 'approval') item.status = approved ? 'approved' : 'rejected'
        }
      })
      get().send({ type: 'approval_response', id, approved })
    },

    newChat: () => {
      get().send({ type: 'new' })
      set((s) => {
        s.messages = []
        s.artifacts = []
        s.activeArtifactId = null
        s.artifactsOpen = false
        s.currentAssistantId = null
        s.busy = false
      })
    },

    resumeChat: (id) => {
      if (get().busy) return
      get().send({ type: 'resume', id })
    },
  })),
)
