import { readFileSync } from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'
import ts from 'typescript'
const moduleUrl = (source) =>
  'data:text/javascript;base64,' +
  Buffer.from(
    ts.transpileModule(source, {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
    }).outputText,
  ).toString('base64')
const booking = moduleUrl(readFileSync(new URL('../src/booking-time.ts', import.meta.url), 'utf8'))
const source = readFileSync(new URL('../src/calendar-grid.ts', import.meta.url), 'utf8').replace(
  "'./booking-time'",
  JSON.stringify(booking),
)
const { monthGrid, gridWindow, dayKey, eventsForDay, loadCalendarRows, calendarCells } =
  await import(moduleUrl(source))
test('month grid starts Monday, ends Sunday, and covers leap days', () => {
  const days = monthGrid('2028-02')
  assert.equal(new Date(days[0]).getUTCDay(), 1)
  assert.equal(new Date(days.at(-1)).getUTCDay(), 0)
  assert.ok(days.includes('2028-02-29'))
  assert.equal(days.length % 7, 0)
  assert.throws(() => monthGrid('2026-13'))
})
test('calendar bounds use local midnight across Canadian daylight-saving changes', () => {
  const span = gridWindow(monthGrid('2026-11'), 'America/Toronto')
  assert.match(span.ends_after, /T00:00:00-04:00$/)
  assert.match(span.starts_before, /T00:00:00-05:00$/)
  assert.equal(dayKey('2026-11-01T02:00:00Z', 'America/Toronto'), '2026-10-31')
})
test('overnight events appear on both days but an exclusive midnight end does not', () => {
  const rows = [
    { id: 1, starts_at: '2026-10-22T23:30:00-04:00', ends_at: '2026-10-23T00:30:00-04:00' },
    { id: 2, starts_at: '2026-10-22T23:30:00-04:00', ends_at: '2026-10-23T00:00:00-04:00' },
  ]
  assert.deepEqual(
    eventsForDay(rows, '2026-10-22', 'America/Toronto').map((r) => r.id),
    [1, 2],
  )
  assert.deepEqual(
    eventsForDay(rows, '2026-10-23', 'America/Toronto').map((r) => r.id),
    [1],
  )
  assert.deepEqual(
    calendarCells(rows, ['2026-10-22', '2026-10-23'], 'America/Toronto').map((c) =>
      c.rows.map((r) => r.id),
    ),
    [[1, 2], [1]],
  )
})
test('all pages are loaded without dropping events after the first 25', async () => {
  const calls = [],
    progress = []
  const result = await loadCalendarRows(
    async (path) => {
      calls.push(path)
      const page = Number(new URL('https://local/' + path).searchParams.get('page'))
      return {
        results: Array.from({ length: page === 3 ? 10 : 25 }, (_, i) => ({
          id: (page - 1) * 25 + i + 1,
        })),
        count: 60,
        next: page < 3 ? 'next' : null,
      }
    },
    'appointments',
    new URLSearchParams({ status: 'scheduled' }),
    () => true,
    (loaded, total) => progress.push([loaded, total]),
  )
  assert.equal(result.length, 60)
  assert.equal(result.at(-1).id, 60)
  assert.equal(calls.length, 3)
  assert.ok(calls.every((path) => path.includes('status=scheduled')))
  assert.deepEqual(progress, [
    [25, 60],
    [50, 60],
    [60, 60],
  ])
})
test('a superseded month cannot publish its response or request another page', async () => {
  let current = true,
    calls = 0,
    progress = 0
  const result = await loadCalendarRows(
    async () => {
      calls++
      current = false
      return { results: [{ id: 1 }], count: 2, next: 'next' }
    },
    'visits',
    new URLSearchParams(),
    () => current,
    () => progress++,
  )
  assert.equal(result, null)
  assert.equal(calls, 1)
  assert.equal(progress, 0)
})
test('page failures reject the load instead of presenting a partial calendar as complete', async () => {
  let calls = 0
  await assert.rejects(
    loadCalendarRows(
      async () => {
        if (++calls === 2) throw new Error('indisponible')
        return { results: [{ id: 1 }], count: 2, next: 'next' }
      },
      'visits',
      new URLSearchParams(),
      () => true,
      () => {},
    ),
    /indisponible/,
  )
})
