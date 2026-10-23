// Administrator-only identity lookup. Missing historical memberships keep their numeric reference.
export async function actorNames(
  portal: ((path: string) => Promise<any>) | undefined,
  workspace: string,
  ids: number[],
): Promise<Record<number, string>> {
  const unique = [...new Set(ids.filter((id) => Number.isSafeInteger(id) && id > 0))].slice(0, 25)
  if (!portal || !unique.length) return {}
  try {
    const response = await portal(`${workspace}/actor-names/?ids=${unique.join(',')}`)
    return Object.fromEntries(
      (response.results || [])
        .filter((row: any) => unique.includes(row.id) && typeof row.name === 'string')
        .map((row: any) => [row.id, row.name]),
    )
  } catch {
    return {}
  }
}
