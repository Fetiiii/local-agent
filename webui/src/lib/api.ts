import type { ConversationMeta, LlmSettings, ModelsResponse, UploadResponse } from './types'

export async function fetchModels(): Promise<ModelsResponse> {
  const r = await fetch('/api/models')
  return r.json()
}

export async function fetchSettings(): Promise<LlmSettings> {
  const r = await fetch('/api/settings')
  return r.json()
}

export async function fetchConversations(): Promise<ConversationMeta[]> {
  const r = await fetch('/api/conversations')
  return r.json()
}

export async function deleteConversation(id: string): Promise<void> {
  await fetch(`/api/conversations/${id}`, { method: 'DELETE' })
}

export async function uploadFile(sessionId: string, file: File): Promise<UploadResponse> {
  const fd = new FormData()
  fd.append('session_id', sessionId)
  fd.append('file', file)
  const r = await fetch('/api/upload', { method: 'POST', body: fd })
  return r.json()
}
