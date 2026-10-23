// Only explicitly attended, non-cancelled appointments consume the prospect quota.
export type AdvisorQuota = {
  id: number
  name: string
  quota: number | null
  booked: number
  attended: number
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
  const counts = new Map<number, any>(usage.results.map((row: any) => [row.advisor_id, row]))
  return new Map(
    quotas.results.map((row: any) => {
      const used = counts.get(row.id)?.attended || 0
      return [
        row.id,
        {
          id: row.id,
          name: row.name,
          quota: row.quota,
          booked: counts.get(row.id)?.booked || 0,
          attended: used,
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
