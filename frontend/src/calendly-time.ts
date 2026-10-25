export const CALENDLY_ZONE = 'America/Toronto'

// Convert a provider instant, never a PC wall-clock time, to Montréal's actual offset.
export function montrealISO(value: string | number) {
  const date = new Date(value)
  const p = Object.fromEntries(
    new Intl.DateTimeFormat('en-CA', {
      timeZone: CALENDLY_ZONE,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hourCycle: 'h23',
    })
      .formatToParts(date)
      .map((part) => [part.type, part.value]),
  )
  const offset = Math.round(
    (Date.UTC(+p.year!, +p.month! - 1, +p.day!, +p.hour!, +p.minute!, +p.second!) -
      date.getTime()) /
      60000,
  )
  const absolute = Math.abs(offset)
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}:${p.second}${offset >= 0 ? '+' : '-'}${String(Math.floor(absolute / 60)).padStart(2, '0')}:${String(absolute % 60).padStart(2, '0')}`
}
