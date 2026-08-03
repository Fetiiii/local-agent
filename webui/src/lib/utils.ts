import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Turn a model id (often a full .gguf path) into a compact display name. */
export function shortModelName(id: string): string {
  const base = id.split(/[/\\]/).pop() || id
  return base.replace(/\.(gguf|bin|safetensors)$/i, '')
}
