// Progressive enhancement: the content and navigation also work without JavaScript.
const menu = document.querySelector('.mobile-menu')
menu?.querySelectorAll('a').forEach((link) => {
  link.addEventListener('click', () => {
    menu.open = false
  })
})
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && menu?.open) {
    menu.open = false
    menu.querySelector('summary')?.focus()
  }
})
if (
  !window.matchMedia('(prefers-reduced-motion: reduce)').matches &&
  'IntersectionObserver' in window
) {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible')
          observer.unobserve(entry.target)
        }
      })
    },
    { threshold: 0.08 },
  )
  document
    .querySelectorAll(
      '.feature-list article, .process-steps article, .offer, .calendar-benefits article',
    )
    .forEach((item) => observer.observe(item))
}
