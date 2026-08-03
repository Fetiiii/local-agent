import DOMPurify from 'dompurify'

/** Sanitize backend-provided HTML (pandas tables, approval detail) before it is
 *  injected via dangerouslySetInnerHTML. */
export function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
}
