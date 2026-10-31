export const appointmentStatusLabels: Record<string, string> = {
  scheduled: 'Planifié',
  rescheduled: 'Reprogrammé',
  performed: 'Rendez-vous validé',
  absent: 'Non honoré',
  not_performed: 'Non effectué — autre motif',
  report_due: 'À renseigner',
  cancelled: 'Annulé',
}
export function appointmentStatus(row: any) {
  return (
    row.business_status_label ||
    appointmentStatusLabels[row.business_status] ||
    (row.status === 'cancelled' ? 'Annulé' : 'Planifié')
  )
}
export function appointmentTone(row: any) {
  return (
    (
      {
        scheduled: 'blue',
        rescheduled: 'violet',
        performed: 'mint',
        absent: 'peach',
        not_performed: 'peach',
        report_due: 'violet',
        cancelled: 'cancelled',
      } as Record<string, string>
    )[row.business_status] || (row.status === 'cancelled' ? 'cancelled' : 'blue')
  )
}
