/** A navigation hint only: normal session and appointment permissions still apply. */
export function appointmentLink(url: URL): number | null {
  const raw = url.searchParams.get('appointment') || ''
  if (url.searchParams.get('workspace') !== 'assurance' || !/^[1-9]\d*$/.test(raw)) return null
  const id = Number(raw)
  return Number.isSafeInteger(id) ? id : null
}
