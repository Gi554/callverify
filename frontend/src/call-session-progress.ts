const QUEBEC_ZONE = 'America/Toronto'

export type CallSessionProgress = {
  day: string
  active: boolean
  visited: number[]
}

export function quebecDay(date = new Date()) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: QUEBEC_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date)
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return `${values.year}-${values.month}-${values.day}`
}

export function callSessionKey(workspace: 'assurance' | 'isolation', owner: string) {
  return `orvia:call-session:${workspace}:${encodeURIComponent(owner || 'unknown')}`
}

export function readCallSession(
  storage: Pick<Storage, 'getItem' | 'removeItem'>,
  key: string,
  day = quebecDay(),
): CallSessionProgress | null {
  try {
    const raw = storage.getItem(key)
    if (!raw) return null
    const value = JSON.parse(raw) as Partial<CallSessionProgress>
    if (
      value.day !== day ||
      value.active !== true ||
      !Array.isArray(value.visited) ||
      value.visited.some((id) => !Number.isSafeInteger(id) || id <= 0)
    ) {
      storage.removeItem(key)
      return null
    }
    return { day, active: true, visited: [...new Set(value.visited)] }
  } catch {
    storage.removeItem(key)
    return null
  }
}

export function writeCallSession(
  storage: Pick<Storage, 'setItem'>,
  key: string,
  progress: CallSessionProgress,
) {
  storage.setItem(key, JSON.stringify(progress))
}

export function clearCallSession(storage: Pick<Storage, 'removeItem'>, key: string) {
  storage.removeItem(key)
}
