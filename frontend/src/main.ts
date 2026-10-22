import { createApp } from 'vue'
import App from './App.vue'
import Portal from './Portal.vue'
import './style.css'
import './login.css'
import './workspace.css'
import './crm-theme.css'
const isPortal=window.location.pathname.startsWith('/crm')
if(isPortal)document.title='AMX — Portail CRM'
if(import.meta.env.VITE_CRM_DEMO === 'true')document.title='AMX — DÉMO FICTIVE'
createApp(isPortal ? Portal : App).mount('#app')
