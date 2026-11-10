export function isDialableNumber(value: string) {
  return (
    /^\+?[0-9\s().\-‐‑‒–—]+$/.test(value.trim()) &&
    /^1?[2-9][0-9]{2}[2-9][0-9]{6}$/.test(value.replace(/\D/g, ''))
  )
}
