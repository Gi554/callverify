// Advisor prospect quotas: the total owed comes from the portal, consumption from the booked
// (non-cancelled) Assurance appointments.
export type AdvisorQuota = {
  id: number
  name: string
  quota: number | null
  booked: number
  remaining: number | null
}

export async function loadQuotas(
  portal: (path: string) => Promise<any>,
  request: (path: string) => Promise<any>,
): Promise<Map<number, AdvisorQuota>> {
  const [quotas, usage] = await Promise.all([
    portal('assurance/advisor-quotas/'),
    request('advisor-usage/'),
  ])
  const booked = new Map<number, number>(
    usage.results.map((row: any) => [row.advisor_id, row.booked]),
  )
  return new Map(
    quotas.results.map((row: any) => {
      const used = booked.get(row.id) || 0
      return [
        row.id,
        {
          id: row.id,
          name: row.name,
          quota: row.quota,
          booked: used,
          remaining: row.quota == null ? null : Math.max(row.quota - used, 0),
        },
      ]
    }),
  )
}

export function quotaText(entry: AdvisorQuota | undefined) {
  if (!entry || entry.quota == null) return ''
  return entry.remaining ? `${entry.remaining} prospect(s) restant(s)` : 'Quota atteint'
}
