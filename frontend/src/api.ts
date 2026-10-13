let csrf = ''
export async function api(path: string, options: RequestInit = {}) {
  if (!csrf && options.method && options.method !== 'GET') {
    const response = await fetch('/api/auth/csrf/', { credentials: 'include' })
    if (!response.ok) throw new Error('Le serveur est indisponible. Vérifiez que le backend est lancé.')
    csrf = (await response.json()).csrfToken
  }
  const headers = new Headers(options.headers)
  if (csrf) headers.set('X-CSRFToken', csrf)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const response = await fetch('/api/' + path, { ...options, headers, credentials: 'include' })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(typeof data.detail === 'string' ? data.detail : Object.values(data).flat().join(' · ') || `Erreur ${response.status}`)
  }
  if (path === 'auth/login/' || path === 'auth/session/' && options.method === 'POST') csrf = ''
  return response.status === 204 ? null : response.json()
}
