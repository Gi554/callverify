import { createApp } from 'vue'
import Portal from './Portal.vue'
import CallSimulation from './CallSimulation.vue'
import { crmEntryRedirect } from './entrypoint'
import './style.css'
import './login.css'
import './workspace.css'
import './crm-theme.css'
import './compact-type.css'
const redirect = crmEntryRedirect(new URL(window.location.href))
if (redirect) window.history.replaceState(null, '', redirect)
document.title = 'Orvia â€” Portail CRM'
if (import.meta.env.VITE_CRM_DEMO === 'true') document.title = 'Orvia â€” DÃ‰MO FICTIVE'
const simulation = new URLSearchParams(window.location.search).get('simulation') === 'appel'
if (simulation) document.title = 'Orvia — Simulation d’appel'
createApp(simulation ? CallSimulation : Portal).mount('#app')
