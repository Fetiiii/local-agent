// Mirror of the backend contract in docs/frontend-api.md.
// Keep this file in sync with that spec — it is the stable seam.

// ── Artifacts (tool_end.artifacts[]) ────────────────────────────────────────
export interface LinkItem {
  title?: string
  link: string
  snippet?: string
}

export type Artifact =
  | { type: 'image'; data: string }
  | { type: 'plotly'; json: string }
  | { type: 'table'; html: string }
  | { type: 'links'; items: LinkItem[] }
  | { type: 'text'; text: string }
  | {
      type: 'file'
      path: string
      name?: string
      // Additive (see docs): richer file preview.
      kind?: 'html' | 'markdown' | 'csv' | 'excel' | 'pdf' | 'text' | 'binary' | string
      text?: string
      table_html?: string
      data?: string // base64 data URI (e.g. PDF), size-capped
    }

export type ArtifactKind = Artifact['type']

// ── Server → client events ──────────────────────────────────────────────────
export type ServerEvent =
  | { type: 'session'; id: string; thread_id: string }
  | { type: 'step'; thought?: string; plan?: string[] }
  | { type: 'thinking'; text?: string; done?: boolean; reset?: boolean }
  | { type: 'plan'; plan: string[] }
  | { type: 'tool_start'; id: string; name: string; args: Record<string, unknown> }
  | { type: 'tool_end'; id: string; name: string; result: string; artifacts?: Artifact[] }
  | { type: 'token'; text: string }
  | { type: 'final'; text: string }
  | { type: 'notice'; text: string; level?: 'info' | 'warn' | 'error' }
  | { type: 'approval_request'; id: string; title: string; detail: string }
  | {
      type: 'history'
      thread_id: string
      messages: { role: string; content: string }[]
      ui?: { messages: ChatMessage[]; artifacts: ArtifactEntry[] } | null
    }
  | { type: 'thread'; id: string }
  | { type: 'done' }

// ── Client → server messages ────────────────────────────────────────────────
export type ClientMessage =
  | { type: 'user_message'; content: string; model?: string; deep_research?: boolean; orchestrate?: boolean }
  | { type: 'approval_response'; id: string; approved: boolean }
  | { type: 'resume'; id: string }
  | { type: 'new' }
  | { type: 'persist'; ui: { messages: ChatMessage[]; artifacts: ArtifactEntry[] } }
  | { type: 'settings'; settings: LlmSettings }

export interface LlmSettings {
  temperature: number
  top_p: number
  max_tokens: number // 0 = unlimited
  max_steps: number
}

// ── REST shapes ─────────────────────────────────────────────────────────────
export interface ModelsResponse {
  provider: string
  models: string[]
  current?: string       // currently-loaded model (llama.cpp)
  manageable?: boolean   // server can hot-swap models (llama.cpp managed)
  error?: string
}

export interface ConversationMeta {
  id: string
  title: string
  updated: number
}

export interface UploadResponse {
  ok: boolean
  type?: 'image' | 'doc'
  name: string
  chunks?: number
  error?: string
}

// ── UI-side view model ──────────────────────────────────────────────────────
export interface PlanItem {
  text: string
  done: boolean
}

export type TimelineItem =
  | { kind: 'step'; id: string; thought: string; streaming?: boolean }
  | {
      kind: 'tool'
      id: string
      name: string
      args: Record<string, unknown>
      result?: string
      status: 'running' | 'done'
      artifactIds: string[]
    }
  | {
      kind: 'terminal'
      id: string
      command: string
      cwd?: string
      output?: string
      status: 'running' | 'done'
      artifactIds: string[]
    }
  | {
      kind: 'approval'
      id: string
      title: string
      detail: string
      status: 'pending' | 'approved' | 'rejected'
    }
  | { kind: 'notice'; id: string; text: string; level: 'info' | 'warn' | 'error' }

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  timeline: TimelineItem[]
  plan: PlanItem[]
  pending: boolean // assistant turn started, nothing visible yet ("düşünüyor…")
  streaming: boolean
  done: boolean
}

export interface ArtifactEntry {
  id: string
  sourceTool: string
  artifact: Artifact
}
