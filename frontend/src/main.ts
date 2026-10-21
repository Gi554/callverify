import { createApp } from 'vue'
import App from './App.vue'
import Portal from './Portal.vue'
import './style.css'
import './login.css'
import './workspace.css'
import './crm-theme.css'
const isPortal=window.location.pathname.startsWith('/crm')
if(isPortal)document.title='AMX — Portail CRM'
createApp(isPortal ? Portal : App).mount('#app')
