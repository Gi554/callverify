import { createApp } from 'vue'
import Portal from './Portal.vue'
import { crmEntryRedirect } from './entrypoint'
import './style.css'
import './login.css'
import './workspace.css'
import './crm-theme.css'
const redirect = crmEntryRedirect(new URL(window.location.href))
if (redirect) window.history.replaceState(null, '', redirect)
document.title = 'Orvia — Portail CRM'
if (import.meta.env.VITE_CRM_DEMO === 'true') document.title = 'Orvia — DÉMO FICTIVE'
createApp(Portal).mount('#app')
