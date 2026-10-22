/** One CRM entry point. Legacy standalone screens no longer have a mount path. */
export function crmEntryRedirect(url: URL): string | null {
  if (url.pathname === '/crm' || url.pathname.startsWith('/crm/')) return null
  // Central invitations/recovery links at / remain usable; old hashes are retired.
  const centralToken = /^#(?:invite|reset)=/.test(url.hash)
  return '/crm' + (centralToken ? url.hash : '')
}
