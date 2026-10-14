<script setup lang="ts">
import { computed, onMounted, onUnmounted, nextTick, ref } from 'vue'
import Workspace from './Workspace.vue'
import { LayoutDashboard, FolderOpen, Upload, Phone, Download, ShieldCheck, Settings2, Search, Bell, CircleHelp, ArrowUpRight, ArrowRight, ChevronRight, ChevronDown, Plus, Check, Clock3, X, LogOut, LogIn, Eye, EyeOff, FileSpreadsheet, CircleCheck, CircleAlert, Menu, LoaderCircle, LockKeyhole, Users, Activity, Sparkles } from 'lucide-vue-next'
import { api } from './api'

type Campaign = { id: number; name: string; source: string; purpose: string; status: string; budget: string; spent: string; created_at: string }
type User = { username: string; superadmin: boolean }
const demo = ref(location.pathname === '/demo')
const user = ref<User | null>(demo.value ? {username:'Alex Martin',superadmin:true} : null)
const page = ref(location.hash.replace('#/','') || 'dashboard'), busy = ref(false), error = ref(''), toast = ref(''), mobileMenu = ref(false)
const username = ref(''), password = ref(''), code = ref(''), showPassword = ref(false), reset = ref(false), email = ref('')
const resetConfirm = ref(location.pathname === '/reset-password' && new URLSearchParams(location.search).has('token'))
const newPassword = ref(''), repeatPassword = ref('')
const showMfa = ref(false)
const workspaceRef=ref<InstanceType<typeof Workspace>|null>(null)
let dashboardTimer:ReturnType<typeof setInterval>|undefined
const stats = ref<any>(null), campaigns = ref<Campaign[]>([]), rows = ref<any[]>([]), jobs = ref<any[]>([]), imports = ref<any[]>([])
const modal = ref(''), selectedCampaign = ref(''), campaignName = ref(''), campaignSource = ref(''), campaignPurpose = ref(''), budget = ref('10')
const uploadFile = ref<File | null>(null), preview = ref<any>(null), mappingPhone = ref(''), mappingName = ref(''), query = ref(''), statusFilter = ref('')
const nav = [{id:'dashboard',label:'Tableau de bord',icon:LayoutDashboard},{id:'campaigns',label:'Campagnes',icon:FolderOpen},{id:'imports',label:'Imports',icon:Upload},{id:'results',label:'Numéros & résultats',icon:Phone},{id:'exports',label:'Exports',icon:Download},{id:'calls',label:'Appels',icon:Phone},{id:'account',label:'Mon compte',icon:ShieldCheck}]
const pageTitle = computed(() => nav.find(n => n.id === page.value)?.label || ({audit:'Journal d’audit',admins:'Administrateurs',exclusions:'Exclusions',settings:'Paramètres'} as Record<string,string>)[page.value])
const visibleCampaigns = computed(() => campaigns.value.filter(c => c.name.toLowerCase().includes(query.value.toLowerCase()) && (!statusFilter.value || c.status === statusFilter.value)))
const completed = computed(() => stats.value?.lookup?.find((s:any) => s.status === 'completed')?.count || 0)
const invalid = computed(() => stats.value?.validity?.find((s:any) => s.validity === 'invalid')?.count || 0)
const valid = computed(() => stats.value?.validity?.find((s:any) => s.validity === 'valid')?.count || 0)
const progress = computed(() => Math.min(100,Math.round(completed.value / (stats.value?.unique_numbers || 1) * 100)))
const demoCampaigns: Campaign[] = [
  {id:1,name:'Prospection · Québec',source:'Fichier commercial',purpose:'Qualification',status:'active',budget:'150.00',spent:'42.80',created_at:'2026-10-13'},
  {id:2,name:'Contacts · Ontario',source:'Liste partenaire',purpose:'Qualification',status:'draft',budget:'100.00',spent:'18.20',created_at:'2026-10-12'},
  {id:3,name:'Base clients · Canada',source:'Base interne',purpose:'Qualification',status:'archived',budget:'200.00',spent:'65.00',created_at:'2026-10-10'}]
async function showNotifications(){try{if(demo.value){notify('Aperçu : aucune alerte réelle.');return}const result=await api('notifications/');notify(result.items.length?result.items.map((r:any)=>r.message).join(' · '):'Aucune erreur de traitement en cours.')}catch(e:any){notify(e.message)}}
function notify(message: string) { toast.value = message; setTimeout(() => toast.value = '', 4500) }
function demoData() {
  campaigns.value = demoCampaigns
  stats.value = {campaigns:3,imports:8,unique_numbers:12480,reserved_cost:'126.00',validity:[{validity:'valid',count:10896},{validity:'invalid',count:584}],lookup:[{status:'completed',count:9876},{status:'error',count:24}]}
  rows.value = [{id:1,name:'Contact fictif A',raw_phone:'(416) 555-0123',e164:'+14165550123',validity:'valid',line_status:'unknown',compliance:'review'}, {id:2,name:'Contact fictif B',raw_phone:'(514) 555-0124',e164:'+15145550124',validity:'valid',line_status:'unknown',compliance:'review'}, {id:3,name:'Format invalide',raw_phone:'invalide',e164:null,validity:'invalid',line_status:'unknown',compliance:'review'}]
  imports.value = [{id:1,campaign:1,status:'completed',created_at:'2026-10-13',report:{total:4500,valid:4216,duplicates:218,invalid:66}},{id:2,campaign:2,status:'completed',created_at:'2026-10-12',report:{total:3280,valid:3140,duplicates:110,invalid:30}}]
  jobs.value = [{id:1,campaign:1,format:'csv',status:'completed',expires_at:'2026-10-14T20:00:00Z'}]
}
async function load() {
  if (demo.value) { demoData(); return }
  try {
    const [s,c,i,e] = await Promise.all([api('dashboard/'),api('campaigns/'),api('imports/'),api('exports/')])
    stats.value=s; campaigns.value=c.results; imports.value=i.results; jobs.value=e.results
  } catch(e:any) { error.value=e.message }
}
async function navigate(id:string) {
  if(!['dashboard','campaigns','imports','results','exports','calls','account','admins','audit','exclusions','settings'].includes(id))id='dashboard'
  if (!user.value?.superadmin && ['admins','audit','exclusions','settings'].includes(id)) id='dashboard'
  page.value=id;error.value='';mobileMenu.value=false
  history.replaceState(null,'',`${demo.value?'/demo':'/'}#/${id}`)
}
function hashChanged(){navigate(location.hash.replace('#/','')||'dashboard')}
async function signIn() {
  busy.value=true; error.value=''
  try { user.value=await api('auth/login/',{method:'POST',body:JSON.stringify({username:username.value,password:password.value,code:code.value})}); password.value=''; await navigate(page.value); await load() }
  catch(e:any) { error.value=e.message; if (/MFA/i.test(e.message)) showMfa.value=true } finally { busy.value=false }
}
async function signOut() {
  try { if(!demo.value) await api('auth/session/',{method:'POST'}); user.value=null; demo.value=false; history.replaceState(null,'','/'); page.value='dashboard' }
  catch(e:any) { error.value=e.message }
}
function openDemo() { demo.value=true; user.value={username:'Alex Martin',superadmin:true}; history.replaceState(null,'','/demo'); demoData() }
async function recover() {
  busy.value=true; error.value=''
  try { const response=await api('auth/reset/request/',{method:'POST',body:JSON.stringify({email:email.value})}); notify(response.detail) }
  catch(e:any) { error.value=e.message } finally {busy.value=false}
}
async function changePassword() {
  if (newPassword.value !== repeatPassword.value) {error.value='Les mots de passe ne correspondent pas.';return}
  busy.value=true; error.value=''
  try {
    const params=new URLSearchParams(location.search)
    await api('auth/reset/confirm/',{method:'POST',body:JSON.stringify({uid:params.get('uid'),token:params.get('token'),password:newPassword.value})})
    resetConfirm.value=false; history.replaceState(null,'','/'); newPassword.value='';repeatPassword.value='';notify('Mot de passe modifié. Vous pouvez vous connecter.')
  } catch(e:any) {error.value=e.message} finally {busy.value=false}
}
async function openModal(kind:string){
  await navigate(({campaign:'campaigns',import:'imports',export:'exports'} as Record<string,string>)[kind])
  await nextTick();await workspaceRef.value?.show(kind)
}
async function createCampaign() {
  busy.value=true; error.value=''
  try {
    if(demo.value) { notify('Aperçu : les données de démonstration ne sont pas enregistrées.'); modal.value=''; return }
    await api('campaigns/',{method:'POST',body:JSON.stringify({name:campaignName.value,source:campaignSource.value,purpose:campaignPurpose.value,budget:budget.value})})
    modal.value=''; campaignName.value=''; await load(); notify('Campagne créée')
  } catch(e:any) {error.value=e.message} finally {busy.value=false}
}
async function upload() {
  if(!uploadFile.value) return
  busy.value=true; error.value=''
  try {
    if(demo.value) { notify('Connectez-vous à votre compte pour importer un fichier.'); return }
    const form=new FormData(); form.append('file',uploadFile.value); form.append('campaign',selectedCampaign.value)
    preview.value=await api('imports/',{method:'POST',body:form}); mappingPhone.value=preview.value.headers.find((h:string)=>/phone|tel/i.test(h)) || preview.value.headers[0]; mappingName.value=''
  } catch(e:any) {error.value=e.message} finally {busy.value=false}
}
async function confirmImport() {
  busy.value=true; error.value=''
  try {
    await api(`imports/${preview.value.id}/confirm/`,{method:'POST',body:JSON.stringify({mapping:{phone:mappingPhone.value,...(mappingName.value?{name:mappingName.value}:{})}})})
    modal.value=''; await load(); notify('Import lancé. Consultez sa progression dans Imports.'); navigate('imports')
  } catch(e:any) {error.value=e.message} finally {busy.value=false}
}
async function exportData() {
  busy.value=true; error.value=''
  try {
    if(demo.value) {notify('Connectez-vous pour générer un export de vos données.'); return}
    await api('exports/',{method:'POST',body:JSON.stringify({campaign:Number(selectedCampaign.value),format:'csv'})}); modal.value=''; await load(); navigate('exports'); notify('Export demandé')
  } catch(e:any) {error.value=e.message} finally {busy.value=false}
}
async function lookup(c:Campaign) {
  if(demo.value) {notify('Connectez-vous pour lancer une vérification.');return}
  try {const result=await api(`campaigns/${c.id}/lookup/`,{method:'POST',body:'{}'}); notify(`${result.scheduled} vérifications planifiées`); await load()} catch(e:any) {error.value=e.message}
}
function label(value:string) { return ({valid:'Valide',invalid:'Invalide',unknown:'Inconnue',review:'À examiner',completed:'Terminé',draft:'Brouillon',archived:'Archivée',active:'En cours',error:'Erreur',pending:'En attente',queued:'En attente'} as Record<string,string>)[value] || value }
function formatNumber(v:number) { return new Intl.NumberFormat('fr-FR').format(v || 0) }
function campaignLabel(id:number) {return campaigns.value.find(c=>c.id===id)?.name || `Campagne ${id}`}
onMounted(async()=> {window.addEventListener('hashchange',hashChanged);dashboardTimer=setInterval(()=>{if(user.value&&!demo.value&&page.value==='dashboard'&&!document.hidden)load()},15000);if(demo.value) {demoData();return} try {user.value=await api('auth/session/');await navigate(page.value);await load()} catch {user.value=null} })
onUnmounted(()=>{clearInterval(dashboardTimer);window.removeEventListener('hashchange',hashChanged)})
</script>

<template>
  <div v-if="!user" class="login-shell">
    <header class="login-header"><a class="brand" href="/"><span class="brand-mark"><Phone :size="22" stroke-width="2.5"/></span>CallVerify<span class="brand-dot">.</span></a><div class="login-header-actions"><span class="login-private"><LockKeyhole :size="15"/> Espace administrateur</span><button class="login-preview-button" @click="openDemo"><LayoutDashboard :size="17"/> Découvrir l’espace</button><button class="login-help" @click="notify('Pour obtenir un compte, contactez le superadministrateur de votre entreprise.')"><CircleHelp :size="18"/> Aide</button></div></header>
    <div class="login-art route-art" aria-hidden="true"><svg viewBox="0 0 420 430" fill="none"><path d="M-25 363L63 350L104 297L96 240L154 191L223 185L244 146L267 133L288 139L322 126L337 69L331 28" stroke="#36382e" stroke-width="4" stroke-linejoin="round"/><path d="M-25 368L65 355L109 298L101 244" stroke="#36382e" stroke-width="1"/><g transform="rotate(-5 231 200)"><rect x="146" y="172" width="207" height="66" rx="6" fill="#f6f5ed" stroke="#36382e" stroke-width="2"/><path d="M167 194L179 205L174 207L169 218L164 216L169 206L164 204Z" stroke="#36382e" stroke-width="2"/><text x="191" y="200" fill="#36382e" font-size="11" font-family="monospace" letter-spacing="1">LA BONNE LISTE,</text><text x="191" y="220" fill="#36382e" font-size="11" font-family="monospace" letter-spacing="1">LE BON CONTACT.</text></g><circle cx="330" cy="28" r="16" fill="#dd792f"/><path d="M324 28L328 32L336 23" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg></div>
    <div class="login-art phone-art" aria-hidden="true"><svg viewBox="0 0 290 280" fill="none"><path d="M65 34C54 29 40 34 34 45L16 77C1 106 38 162 78 202C118 242 175 278 203 261L236 243C247 237 252 223 246 212L223 169C218 159 206 155 196 160L166 176C152 170 137 158 123 144C110 131 97 115 92 102L107 73C112 62 108 51 98 46Z" fill="#9380dc"/><path d="M174 30C211 38 238 65 246 101M176 65C195 70 208 84 212 102" stroke="#9380dc" stroke-width="14" stroke-linecap="round"/></svg><span>PRÊT À FAIRE LE LIEN ?</span></div>
    <div class="login-art burst-art" aria-hidden="true"><svg viewBox="0 0 160 120"><path d="M20 91L139 91M38 76L29 65M56 65L43 39M77 59L73 22M99 61L109 29M118 73L137 51" fill="none" stroke="#bac34c" stroke-width="12"/></svg></div>
    <div class="login-art star-art" aria-hidden="true"><svg viewBox="0 0 100 100"><path d="M50 5L60 35L89 25L72 50L94 68L63 66L53 97L43 69L12 81L28 55L4 36L37 38Z" fill="#ef8739"/></svg></div>
    <div class="login-art bottom-route-art" aria-hidden="true"><svg viewBox="0 0 400 260" fill="none"><path d="M44 174L23 196L29 218L65 209L96 180L152 239L275 218L256 106L277 78L386 91L416 61" stroke="#36382e" stroke-width="4" stroke-linejoin="round"/><g transform="rotate(4 270 90)"><rect x="185" y="54" width="200" height="45" rx="23" fill="#f6f5ed" stroke="#36382e" stroke-width="2"/><circle cx="209" cy="76" r="8" stroke="#36382e" stroke-width="2"/><path d="M204 76L208 80L214 73" stroke="#36382e" stroke-width="2"/><text x="227" y="80" fill="#36382e" font-family="monospace" font-size="10">DES DONNÉES PLUS FIABLES</text></g><circle cx="44" cy="174" r="16" fill="#53661c"/><path d="M39 174L43 178L50 170" stroke="#fff" stroke-width="2"/></svg></div>
    <main class="login-main">
      <div class="login-form-wrap"><span class="welcome-icon"><Phone :size="23" stroke-width="2.5"/></span><h2>{{ resetConfirm ? 'Un nouveau départ' : reset ? 'Retrouvons votre accès' : 'Heureux de vous revoir !' }}</h2><p>{{ resetConfirm ? 'Choisissez un mot de passe sécurisé pour votre compte.' : reset ? 'Nous vous enverrons un lien pour choisir un nouveau mot de passe.' : 'Connectez-vous à votre espace CallVerify' }}</p>
        <form v-if="resetConfirm" @submit.prevent="changePassword"><label for="new-password">Nouveau mot de passe</label><input id="new-password" v-model="newPassword" type="password" autocomplete="new-password" minlength="12" placeholder="Au moins 12 caractères" required><label for="repeat-password">Confirmer le mot de passe</label><input id="repeat-password" v-model="repeatPassword" type="password" autocomplete="new-password" minlength="12" placeholder="Saisissez le mot de passe à nouveau" required><p v-if="error" class="error" role="alert">{{error}}</p><button class="primary login-submit" :disabled="busy">Enregistrer le mot de passe <ArrowRight :size="18"/></button></form>
        <form v-else-if="!reset" @submit.prevent="signIn"><label for="username">Votre identifiant</label><div class="username-input"><input id="username" v-model="username" autocomplete="username" placeholder="Votre identifiant administrateur" required><button v-if="username" type="button" aria-label="Effacer l’identifiant" @click="username=''"><X :size="20"/></button></div>
          <div class="label-line"><label for="password">Mot de passe</label><button type="button" class="text-button" @click="reset=true;error=''">Mot de passe oublié ?</button></div><div class="password-input"><input id="password" v-model="password" :type="showPassword?'text':'password'" autocomplete="current-password" placeholder="Saisissez votre mot de passe" required><button type="button" :aria-label="showPassword?'Masquer le mot de passe':'Afficher le mot de passe'" @click="showPassword=!showPassword"><EyeOff v-if="showPassword" :size="19"/><Eye v-else :size="19"/></button></div>
          <div class="mfa-section"><button type="button" class="mfa-toggle" :aria-expanded="showMfa" aria-controls="mfa-code" @click="showMfa=!showMfa"><ShieldCheck :size="14"/> Code de sécurité <ChevronDown :size="13" :class="{rotated:showMfa}"/></button><div v-if="showMfa" id="mfa-code"><label for="code">Code de votre application d’authentification</label><input id="code" v-model="code" inputmode="numeric" autocomplete="one-time-code" maxlength="19" placeholder="Code MFA ou code de secours"></div></div>
          <p v-if="error" class="error" role="alert">{{error}}</p><button class="primary login-submit" :disabled="busy"><LoaderCircle v-if="busy" class="spin" :size="18"/><LogIn v-else :size="21"/>{{busy?'Connexion…':'Se connecter'}}</button>
        </form>
        <form v-else @submit.prevent="recover"><label for="email">Adresse e-mail</label><input id="email" v-model="email" type="email" autocomplete="email" placeholder="vous@entreprise.com" required><p v-if="error" class="error" role="alert">{{error}}</p><button class="primary login-submit" :disabled="busy">Envoyer le lien <ArrowRight :size="18"/></button><button type="button" class="text-button back-login" @click="reset=false;error=''">Retour à la connexion</button></form>
        <div class="access-note"><LockKeyhole :size="16"/><p>Accès réservé aux administrateurs autorisés.<br>Vos listes restent dans votre espace privé.</p></div><button class="demo-link" @click="openDemo">Découvrir un aperçu du tableau de bord <ArrowUpRight :size="15"/></button>
      </div>
    </main>
    <footer class="login-footer"><span>© {{new Date().getFullYear()}} CallVerify</span><span><ShieldCheck :size="13"/> Vos données restent dans votre espace privé.</span><span>Conçu pour vos campagnes au Canada</span></footer>
  </div>
  <div v-else class="app-shell">
    <aside :class="['sidebar',{open:mobileMenu}]"><a class="brand" href="#" @click.prevent="navigate('dashboard')"><span class="brand-mark"><Phone :size="22" stroke-width="2.5"/></span>CallVerify<span class="brand-dot">.</span></a><div class="workspace"><span class="workspace-avatar">C</span><div><strong>Mon espace</strong><small>Qualification · Canada</small></div><span class="pill mini">CA</span></div>
      <nav><span class="nav-section">VOTRE ACTIVITÉ</span><button v-for="item in nav" :key="item.id" :class="['nav-item',{selected:page===item.id}]" @click="navigate(item.id)"><component :is="item.icon" :size="21" stroke-width="1.7"/><span>{{item.label}}</span><span v-if="item.id==='imports' && imports.length" class="nav-count">{{imports.length}}</span></button>
        <template v-if="user.superadmin"><span class="nav-section administration">ADMINISTRATION</span><button :class="['nav-item',{selected:page==='admins'}]" @click="navigate('admins')"><Users :size="21" stroke-width="1.7"/>Administrateurs</button><button :class="['nav-item',{selected:page==='audit'}]" @click="navigate('audit')"><ShieldCheck :size="21" stroke-width="1.7"/>Journal d’audit</button><button :class="['nav-item',{selected:page==='exclusions'}]" @click="navigate('exclusions')"><ShieldCheck :size="21"/>Exclusions</button><button :class="['nav-item',{selected:page==='settings'}]" @click="navigate('settings')"><Settings2 :size="21"/>Paramètres</button></template></nav>
      <div class="sidebar-bottom"><button class="profile" @click="signOut" title="Se déconnecter"><span class="avatar">{{user.username.slice(0,2).toUpperCase()}}</span><span><strong>{{user.username}}</strong><small>{{demo?'Compte de démonstration':user.superadmin?'Super administrateur':'Administrateur'}}</small></span><LogOut :size="18"/></button></div>
    </aside>
    <main class="main-content"><header class="topbar"><div class="breadcrumb"><button class="mobile-menu icon-button" aria-label="Ouvrir le menu" @click="mobileMenu=!mobileMenu"><Menu :size="22"/></button><span>Mon espace</span><ChevronRight :size="14"/><strong>{{pageTitle}}</strong></div><div class="top-actions"><span v-if="demo" class="pill demo-pill"><Sparkles :size="13"/> Aperçu démo</span><span class="connection"><span class="live-dot"></span>{{demo?'Données fictives':'Espace connecté'}}</span><button class="icon-button" aria-label="Aide" @click="notify('Commencez par créer une campagne, puis importez un fichier CSV ou Excel.')"><CircleHelp :size="21"/></button><button class="icon-button notification" aria-label="Notifications" @click="showNotifications"><Bell :size="21"/></button></div></header>
      <div class="page-content"><div v-if="page==='dashboard'" class="page-heading"><div><h1>{{page==='dashboard'?`Bonjour, ${user.username.split(' ')[0]} 👋`:pageTitle}}</h1><p>{{page==='dashboard'?'Voici ce qui se passe dans vos campagnes aujourd’hui.':'Retrouvez et gérez les données de votre espace.'}}</p></div><button v-if="['dashboard','campaigns'].includes(page)" class="primary" @click="openModal('campaign')"><Plus :size="18"/> Nouvelle campagne</button></div>
        <p v-if="error && !modal" class="error" role="alert">{{error}}</p>
        <template v-if="page==='dashboard'"><div class="overview-label">VUE D’ENSEMBLE <span>{{demo?'Exemple de données':'Toutes vos campagnes'}}</span></div><div class="kpi-grid"><article class="kpi-card"><span class="kpi-icon blue"><Phone :size="20"/></span><span>Numéros uniques</span><strong>{{formatNumber(stats?.unique_numbers)}}</strong><small>Dans votre base de contacts</small></article><article class="kpi-card"><span class="kpi-icon green"><CircleCheck :size="20"/></span><span>Vérifications terminées</span><strong>{{formatNumber(completed)}}</strong><small><span class="tiny-dot green-dot"></span> Contrôles Lookup effectués</small></article><article class="kpi-card"><span class="kpi-icon orange"><CircleAlert :size="20"/></span><span>Numéros invalides</span><strong>{{formatNumber(invalid)}}</strong><small>À retirer de vos listes</small></article><article class="kpi-card"><span class="kpi-icon purple"><FileSpreadsheet :size="20"/></span><span>Fichiers importés</span><strong>{{formatNumber(stats?.imports)}}</strong><small>Des listes centralisées</small></article></div>
          <div class="dashboard-grid"><div class="main-column"><section class="card task-card"><div class="card-header"><h2>À vous de jouer</h2><span class="pill muted">3 étapes pour avancer</span></div><button class="task-row" @click="openModal('import')"><span class="task-icon blue"><Upload :size="22"/></span><span class="task-text"><strong>Importer une nouvelle liste</strong><small>Ajoutez vos contacts depuis un fichier CSV ou Excel.</small></span><span class="task-end">Commencer <ChevronRight :size="17"/></span></button><button class="task-row" @click="navigate('campaigns')"><span class="task-icon purple"><ShieldCheck :size="22"/></span><span class="task-text"><strong>Lancer vos vérifications</strong><small>Nettoyez vos numéros et vérifiez leur validité technique.</small></span><span class="task-end">Vérifier <ChevronRight :size="17"/></span></button><button class="task-row" @click="openModal('export')"><span class="task-icon green"><Download :size="22"/></span><span class="task-text"><strong>Préparer votre prochain export</strong><small>Retrouvez une liste propre, prête à être transmise.</small></span><span class="task-end">Exporter <ChevronRight :size="17"/></span></button></section>
            <section class="card"><div class="card-header"><h2>Vos campagnes récentes <span class="heading-count">{{campaigns.length}}</span></h2><button class="text-button" @click="navigate('campaigns')">Tout voir <ChevronRight :size="16"/></button></div><div v-if="!campaigns.length" class="empty-state"><FolderOpen :size="30"/><strong>Votre première campagne vous attend</strong><p>Créez une campagne pour commencer à qualifier vos contacts.</p><button class="text-button" @click="openModal('campaign')">Créer une campagne <ArrowRight :size="16"/></button></div><div v-for="c in campaigns.slice(0,3)" :key="c.id" class="campaign-row"><span class="campaign-icon"><FolderOpen :size="21"/></span><div><strong>{{c.name}}</strong><small>{{c.source}}</small></div><span :class="['pill',c.status==='active'?'green-pill':'muted']"><span class="tiny-dot"></span>{{label(c.status)}}</span><button class="icon-button" aria-label="Voir les campagnes" @click="navigate('campaigns')"><ChevronRight :size="18"/></button></div></section>
            <section class="tip-card"><span class="tip-icon"><Sparkles :size="22"/></span><div><strong>Une bonne campagne commence par une bonne liste.</strong><p>La validité d’un numéro ne garantit pas qu’une personne répondra. Gardez une vue claire sur chaque résultat.</p></div><ShieldCheck class="tip-decoration" :size="70" stroke-width="1"/></section>
          </div><div class="right-column"><section class="card"><div class="card-header"><h2>Votre qualification</h2><Activity :size="19" class="subtle"/></div><div class="quality-body"><div class="quality-title"><strong>{{progress}}<span>%</span></strong><span>des numéros vérifiés</span></div><div class="progress-track"><div :style="{width:progress+'%'}"></div></div><div class="legend-row"><span><i class="legend-dot blue-dot"></i>Techniquement valides</span><strong>{{formatNumber(valid)}}</strong></div><div class="legend-row"><span><i class="legend-dot orange-dot"></i>Invalides</span><strong>{{formatNumber(invalid)}}</strong></div><div class="legend-row"><span><i class="legend-dot gray-dot"></i>Restant à vérifier</span><strong>{{formatNumber(Math.max(0,(stats?.unique_numbers||0)-completed))}}</strong></div><button class="secondary full-width" @click="navigate('results')">Consulter les résultats <ArrowRight :size="16"/></button></div></section>
            <section class="card"><div class="card-header"><h2>Observations Voice</h2></div><div class="quality-body"><div class="legend-row"><span>Tentatives enregistrées</span><strong>{{stats?.voice?.attempts||0}}</strong></div><div class="legend-row"><span>Sonneries observées</span><strong>{{stats?.voice?.rang||0}}</strong></div><div class="legend-row"><span>Connexions observées</span><strong>{{stats?.voice?.answered||0}}</strong></div><p class="subtle">Une connexion ne garantit pas une réponse humaine. Résultats distincts de Lookup.</p><div v-for="item in stats?.voice?.statuses||[]" :key="item.status" class="legend-row"><span>{{({busy:'Occupé','no-answer':'Sans réponse',failed:'Échec',completed:'Connexion terminée',ringing:'Sonnerie','in-progress':'Connecté'} as any)[item.status]||item.status}}</span><strong>{{item.count}}</strong></div><div v-for="item in stats?.voice?.amd||[]" :key="item.amd" class="legend-row"><span>AMD : {{item.amd}} (estimation)</span><strong>{{item.count}}</strong></div></div></section><section class="card"><div class="card-header"><h2>Budget de vos campagnes</h2></div><div class="budget-body"><span class="subtle">Coût réservé estimé</span><strong>{{Number(stats?.reserved_cost||0).toLocaleString('fr-FR',{minimumFractionDigits:2})}} <span>unités</span></strong><p>Dans la devise de votre compte fournisseur. Le coût final peut varier.</p><button class="text-button" @click="navigate('campaigns')">Voir les budgets <ChevronRight :size="16"/></button></div></section><div class="private-note"><ShieldCheck :size="18"/><p>Les appels restent désactivés.<br>La qualification technique est indépendante de l’autorisation d’appeler.</p></div>
          </div></div></template>
        <Workspace v-else ref="workspaceRef" :page="page" :demo="demo" :superadmin="user.superadmin" :campaigns="campaigns" @changed="load" @notify="notify" />
        <footer class="dashboard-footer"><span>CallVerify · Votre espace de qualification</span><span><ShieldCheck :size="13"/> Accès privé et sécurisé</span></footer>
      </div>
    </main>
  </div>
  <div v-if="toast" class="toast" role="status"><CircleCheck :size="19"/>{{toast}}<button class="icon-button" aria-label="Fermer la notification" @click="toast=''"><X :size="16"/></button></div>
</template>
