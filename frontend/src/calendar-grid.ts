import { bookingInterval } from './booking-time'
const DAY = 86400000
const formatters = new Map<string, Intl.DateTimeFormat>()
export function dayKey(value: string | Date, zone: string) {
  if (!formatters.has(zone))
    formatters.set(
      zone,
      new Intl.DateTimeFormat('en-CA', {
        timeZone: zone,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
      }),
    )
  const parts = Object.fromEntries(
    formatters
      .get(zone)!
      .formatToParts(new Date(value))
      .map((p) => [p.type, p.value]),
  )
  return `${parts.year}-${parts.month}-${parts.day}`
}
export function monthGrid(month: string) {
  const match = /^(\d{4})-(\d{2})$/.exec(month)
  if (!match || +match[2]! < 1 || +match[2]! > 12) throw new Error('Mois invalide')
  const first = Date.UTC(+match[1]!, +match[2]! - 1, 1),
    last = Date.UTC(+match[1]!, +match[2]!, 0)
  const start = first - ((new Date(first).getUTCDay() + 6) % 7) * DAY
  const end = last + (7 - ((new Date(last).getUTCDay() + 6) % 7)) * DAY
  return Array.from({ length: (end - start) / DAY }, (_, i) =>
    new Date(start + i * DAY).toISOString().slice(0, 10),
  )
}
export function gridWindow(days: string[], zone: string) {
  const next = new Date(Date.parse(days[days.length - 1]! + 'T00:00:00Z') + DAY)
    .toISOString()
    .slice(0, 10)
  return {
    ends_after: bookingInterval(days[0]! + 'T00:00', zone, 30).starts_at,
    starts_before: bookingInterval(next + 'T00:00', zone, 30).starts_at,
  }
}
export function eventsForDay(rows: any[], day: string, zone: string) {
  return rows.filter(
    (row) =>
      dayKey(row.starts_at, zone) <= day &&
      dayKey(new Date(Date.parse(row.ends_at) - 1), zone) >= day,
  )
}
export function calendarCells(rows: any[], days: string[], zone: string) {
  const ranges = rows.map((row) => ({
    row,
    first: dayKey(row.starts_at, zone),
    last: dayKey(new Date(Date.parse(row.ends_at) - 1), zone),
  }))
  return days.map((day) => ({
    day,
    rows: ranges
      .filter((range) => range.first <= day && range.last >= day)
      .map((range) => range.row),
  }))
}
export async function loadCalendarRows(
  request: (path: string) => Promise<any>,
  path: string,
  query: URLSearchParams,
  current: () => boolean,
  progress: (loaded: number, total: number) => void,
) {
  const collected: any[] = []
  let page = 1,
    next = true
  while (next && current()) {
    const data = await request(`${path}/?${query}&page=${page}`)
    if (!current()) return null
    collected.push(...data.results)
    progress(collected.length, data.count)
    next = !!data.next
    page++
  }
  return current() ? [...new Map(collected.map((row) => [row.id, row])).values()] : null
}
