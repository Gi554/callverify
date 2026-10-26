<script setup lang="ts">
import {
  Phone,
  ShieldCheck,
  Home,
  ArrowUpRight,
  ArrowRight,
  LogOut,
  LockKeyhole,
  ContactRound,
  CalendarDays,
  ChartNoAxesCombined,
  Layers,
} from 'lucide-vue-next';

defineProps<{
  username: string;
  spaces: { workspace: string; role: string }[];
  busy: boolean;
  error: string;
}>();
const emit = defineEmits<{ enter: [workspace: string]; logout: [] }>();
const labels: Record<string, string> = {
  administrator: 'Administrateur',
  setter: 'Setter',
  advisor: 'Conseiller',
  client: 'Client',
  closer: 'Closer',
};
</script>

<template>
  <div class="login-shell workspace-welcome">
    <header class="login-header">
      <a class="brand" href="/crm" aria-label="Orvia, accueil">
        <span class="brand-mark"><Phone :size="22" stroke-width="2.5" /></span>
        Orvia<span class="brand-dot">.</span>
      </a>
      <button class="workspace-signout" type="button" :disabled="busy" @click="emit('logout')">
        <LogOut :size="16" />Se déconnecter
      </button>
    </header>

    <main class="workspace-welcome-main" :aria-busy="busy">
      <div class="workspace-intro">
        <span class="workspace-session"><span></span> VOUS ÊTES CONNECTÉ</span>
        <h1>Un nouveau jour.<br />De belles <span>connexions.</span></h1>
        <p>
          Choisissez votre espace et retrouvez votre équipe,<br class="workspace-desktop-break" />
          vos contacts et vos prochaines actions.
        </p>
        <div class="workspace-account">
          <span class="workspace-avatar">{{ username.slice(0, 1).toUpperCase() }}</span
          ><span :title="username">{{ username }}</span
          ><ShieldCheck :size="16" />
        </div>
      </div>

      <div class="workspace-options">
        <div class="workspace-options-heading">
          <span>VOS ESPACES</span
          ><span
            >{{ spaces.length }} accès {{ spaces.length > 1 ? 'disponibles' : 'disponible' }}</span
          >
        </div>
        <p v-if="error" class="workspace-error" role="alert">{{ error }}</p>
        <div class="workspace-options-grid">
          <button
            v-for="item in spaces"
            :key="item.workspace"
            type="button"
            class="workspace-choice"
            :class="{ 'workspace-choice-lilac': item.workspace === 'isolation' }"
            :disabled="busy"
            @click="emit('enter', item.workspace)"
          >
            <span class="workspace-choice-top"
              ><span class="workspace-choice-icon"
                ><ShieldCheck v-if="item.workspace === 'assurance'" :size="29" /><Home
                  v-else
                  :size="29" /></span
              ><span class="workspace-role">{{ labels[item.role] || item.role }}</span></span
            >
            <span class="workspace-choice-title"
              >{{ item.workspace === 'assurance' ? 'Assurance' : 'Isolation'
              }}<ArrowUpRight :size="26"
            /></span>
            <span class="workspace-choice-description">{{
              item.workspace === 'assurance'
                ? 'Le bon contact. Le bon conseil.'
                : 'Des projets qui prennent forme.'
            }}</span>
            <span class="workspace-choice-features"
              ><span><ContactRound :size="15" />Prospects</span
              ><span
                ><CalendarDays :size="15" />{{
                  item.workspace === 'assurance' ? 'Rendez-vous' : 'Visites'
                }}</span
              ><span><ChartNoAxesCombined :size="15" />Suivi</span></span
            >
            <span class="workspace-choice-open"
              >Ouvrir mon espace<span><ArrowRight :size="19" /></span
            ></span>
          </button>
        </div>
        <div v-if="!spaces.length" class="workspace-empty" role="status">
          <Layers :size="28" />
          <h2>Votre espace se prépare.</h2>
          <p>Aucun accès actif pour le moment. Contactez votre administrateur.</p>
        </div>
        <p class="workspace-access-note">
          <LockKeyhole :size="14" />Seuls les espaces autorisés sur votre compte sont affichés.
        </p>
        <p v-if="busy" role="status">Ouverture de votre espace…</p>
      </div>
      <div class="workspace-flourish" aria-hidden="true">
        <span>ON GARDE LE LIEN.</span
        ><svg viewBox="0 0 170 75" fill="none">
          <path
            d="M4 46C36 9 72 4 84 24C99 51 52 75 45 51C38 27 119 12 158 45M143 28L160 45L139 50"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </div>
    </main>
    <footer class="workspace-welcome-footer">
      <span>© {{ new Date().getFullYear() }} Orvia</span
      ><a href="/confidentialite/">Confidentialité</a
      ><span><LockKeyhole :size="13" />Votre espace de travail, en toute confiance.</span>
    </footer>
  </div>
</template>

<style scoped>
.workspace-welcome {
  min-height: 100dvh;
  background: #f6f5ed;
  color: #262820;
}
.workspace-welcome .login-header {
  padding: 28px 4vw;
}
.workspace-signout {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  border: 1px solid #d9dccd;
  border-radius: 30px;
  padding: 11px 17px;
  background: transparent;
  color: #535c40;
  font-size: 13px;
}
.workspace-signout:hover {
  background: #eceee0;
}
.workspace-welcome-main {
  position: relative;
  width: min(100% - 64px, 1040px);
  margin: auto;
  padding: 35px 0 70px;
}
.workspace-intro {
  text-align: center;
}
.workspace-session {
  display: inline-flex;
  gap: 9px;
  align-items: center;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #5b6745;
}
.workspace-session > span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #53661c;
  box-shadow: 0 0 0 4px #53661c12;
}
.workspace-intro h1 {
  margin: 22px 0 18px;
  font-size: clamp(36px, 4.5vw, 58px);
  line-height: 1.1;
  letter-spacing: -2.5px;
  font-weight: 750;
  color: #2c3026;
}
.workspace-intro h1 > span {
  color: #53661c;
}
.workspace-intro > p {
  color: #77796a;
  line-height: 1.7;
  font-size: 15px;
  margin: 0;
}
.workspace-account {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  max-width: 100%;
  margin-top: 22px;
  color: #5c654b;
  font-size: 12px;
}
.workspace-account > span:nth-child(2) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.workspace-avatar {
  display: grid;
  place-items: center;
  flex-shrink: 0;
  width: 29px;
  height: 29px;
  background: #e7e1f4;
  color: #685293;
  border-radius: 50%;
  font-weight: 700;
}
.workspace-options {
  margin-top: 44px;
}
.workspace-options-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
  color: #77796a;
  font-size: 12px;
}
.workspace-options-heading > span:first-child {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1.8px;
  color: #555e44;
}
.workspace-options-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 310px), 1fr));
  gap: 24px;
}
.workspace-choice {
  --accent: #53661c;
  --tile: #edf0df;
  --line: #d7dfc2;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 29px;
  border: 1px solid var(--line);
  border-radius: 22px;
  background: var(--tile);
  color: #2c3423;
  text-align: left;
  box-shadow: 0 5px 0 #53661c06;
  transition:
    transform 180ms ease,
    box-shadow 180ms ease,
    border-color 180ms ease;
}
.workspace-choice-lilac {
  --accent: #6a529d;
  --tile: #eee8f6;
  --line: #ddd2eb;
  color: #392e48;
}
.workspace-choice:hover:not(:disabled) {
  transform: translateY(-4px);
  border-color: var(--accent);
  box-shadow: 0 14px 30px #3537280d;
}
.workspace-choice:focus-visible,
.workspace-signout:focus-visible,
.workspace-welcome a:focus-visible {
  outline: 3px solid #dd792f;
  outline-offset: 5px;
}
.workspace-choice:disabled,
.workspace-signout:disabled {
  opacity: 0.6;
  cursor: wait;
}
.workspace-choice-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.workspace-choice-icon {
  display: grid;
  place-items: center;
  width: 54px;
  height: 54px;
  border-radius: 16px;
  background: #ffffff9c;
  color: var(--accent);
}
.workspace-role {
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 6px 11px;
  color: var(--accent);
  font-size: 11px;
  font-weight: 600;
  background: #ffffff45;
}
.workspace-choice-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 26px;
  font-size: 28px;
  font-weight: 750;
  letter-spacing: -0.8px;
}
.workspace-choice-title > svg {
  color: var(--accent);
}
.workspace-choice-description {
  display: block;
  font-size: 13px;
  opacity: 0.75;
  margin-top: 8px;
  line-height: 1.6;
}
.workspace-choice-features {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin: 22px 0 26px;
  color: var(--accent);
  font-size: 11px;
}
.workspace-choice-features > span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.workspace-choice-open {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 19px;
  border-top: 1px solid var(--line);
  font-size: 13px;
  font-weight: 700;
  color: var(--accent);
}
.workspace-choice-open > span {
  display: grid;
  place-items: center;
  width: 33px;
  height: 33px;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
}
.workspace-access-note {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: center;
  color: #7c8070;
  font-size: 11px;
  margin: 23px 0 0;
  line-height: 1.6;
}
.workspace-empty {
  display: grid;
  justify-items: center;
  gap: 12px;
  padding: 36px 20px;
  border: 1px dashed #c6ceaf;
  border-radius: 20px;
  text-align: center;
  color: #626d4b;
}
.workspace-empty h2 {
  font-size: 20px;
  margin: 0;
}
.workspace-empty p {
  font-size: 14px;
  margin: 0;
}
.workspace-error {
  padding: 14px 18px;
  border-radius: 12px;
  background: #fce2d1;
  color: #893d17;
}
.workspace-flourish {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 22px;
  color: #9380bc;
}
.workspace-flourish > span {
  font-family: monospace;
  font-size: 10px;
  letter-spacing: 1px;
  transform: rotate(-4deg);
}
.workspace-flourish svg {
  width: 110px;
  height: 50px;
}
.workspace-welcome-footer {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 18px;
  padding: 20px 4vw;
  border-top: 1px solid #e5e5d8;
  color: #7d806e;
  font-size: 11px;
}
.workspace-welcome-footer > span:last-child {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}
.workspace-welcome-footer a {
  color: #596449;
  text-decoration: underline;
  text-underline-offset: 3px;
}
@media (max-width: 600px) {
  .workspace-welcome .login-header {
    padding: 22px 20px;
    gap: 12px;
  }
  .workspace-signout {
    padding: 9px 12px;
    font-size: 11px;
  }
  .workspace-welcome-main {
    width: calc(100% - 40px);
    padding: 30px 0 36px;
  }
  .workspace-intro h1 {
    letter-spacing: -1.5px;
  }
  .workspace-desktop-break {
    display: none;
  }
  .workspace-options {
    margin-top: 32px;
  }
  .workspace-choice {
    padding: 24px;
  }
  .workspace-welcome-footer {
    justify-content: center;
    text-align: center;
    padding: 20px;
  }
  .workspace-access-note {
    align-items: flex-start;
    text-align: center;
  }
  .workspace-access-note > svg {
    flex-shrink: 0;
    margin-top: 2px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .workspace-choice {
    transition: none;
  }
  .workspace-choice:hover:not(:disabled) {
    transform: none;
  }
}
</style>
