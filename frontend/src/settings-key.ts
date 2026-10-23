// Stable keys accepted by the API: lowercase letter first, then letters, digits or underscores.
export function keyFromLabel(label: string, prefix: string) {
  const slug = label
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
  const key = /^[a-z]/.test(slug) ? slug : `${prefix}_${slug}`.replace(/_+$/, '')
  return key.slice(0, 40).replace(/_+$/, '')
}

export function uniqueKey(base: string, taken: string[]) {
  if (!taken.includes(base)) return base
  for (let index = 2; ; index++) {
    const suffix = `_${index}`
    const candidate = base.slice(0, 40 - suffix.length) + suffix
    if (!taken.includes(candidate)) return candidate
  }
}
