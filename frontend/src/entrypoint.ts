/** One CRM entry point. Legacy standalone screens no longer have a mount path. */
export function crmEntryRedirect(url: URL): string | null {
  if (url.pathname === '/crm' || url.pathname.startsWith('/crm/')) {
    if (!url.searchParams.has('simulation')) return null
    const target = new URL(url)
    target.searchParams.delete('simulation')
    return target.pathname + target.search + target.hash
  }
  // Central invitations/recovery links at / remain usable; old hashes are retired.
  const centralToken = /^#(?:invite|reset)=/.test(url.hash)
  return '/crm' + (centralToken ? url.hash : '')
}
