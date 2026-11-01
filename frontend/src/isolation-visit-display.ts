export function visitName(row: any) {
  return row.c2_snapshot?.fields?.full_name || row.prospect?.name || row.name || 'Dossier sans nom'
}
export function initials(name: string) {
  return name
    .replace(/^DÉMO\s*[·-]?\s*/i, '')
    .split(/[\s·]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
}
export function visitStatus(row: any) {
  if (row.status === 'cancelled') return row.next_visit_id ? 'Reprogrammé' : 'Annulé'
  if (row.result?.outcome === 'unqualified') return 'Non qualifié'
  if (row.result?.performed === true)
    return row.result.closed === true
      ? 'Présenté · closé'
      : row.result.closed === false
        ? 'Présenté · non closé'
        : 'Vente à préciser'
  if (row.result?.performed === false) return 'Non présenté'
  return row.result_due ? 'Résultat à renseigner' : 'À venir'
}
export function visitTone(row: any) {
  if (row.status === 'cancelled') return 'muted'
  if (row.result?.outcome === 'unqualified') return 'purple'
  if (row.result?.performed === true) return 'green'
  if (row.result?.performed === false || row.result_due) return 'amber'
  return 'blue'
}
export function visitDay(value: string) {
  return new Intl.DateTimeFormat('fr-CA', { timeZone: 'America/Toronto', day: '2-digit' }).format(
    new Date(value),
  )
}
export function visitMonth(value: string) {
  return new Intl.DateTimeFormat('fr-CA', { timeZone: 'America/Toronto', month: 'short' }).format(
    new Date(value),
  )
}
export function visitTime(value: string) {
  return new Intl.DateTimeFormat('fr-CA', {
    timeZone: 'America/Toronto',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}
