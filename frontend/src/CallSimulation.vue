<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { Phone, RotateCcw, ShieldCheck } from 'lucide-vue-next';
import CallCountdownModal from './CallCountdownModal.vue';
import SidePanel from './SidePanel.vue';
import AssuranceContactEditor from './AssuranceContactEditor.vue';
import { createCallSimulation } from './call-simulation';
const seconds = ref<number | null>(10),
  opened = ref(false),
  stopped = ref(false),
  busy = ref(false);
const demo = ref(createCallSimulation());
const editor = ref<InstanceType<typeof AssuranceContactEditor> | null>(null);
let timer: ReturnType<typeof setInterval> | null = null;
function clear() {
  if (timer) clearInterval(timer);
  timer = null;
  seconds.value = null;
}
function launch() {
  clear();
  opened.value = true;
}
function stop() {
  clear();
  stopped.value = true;
}
function restart() {
  clear();
  stopped.value = false;
  opened.value = false;
  try {
    sessionStorage.removeItem(`amx-call:assurance:${demo.value.contact.id}`);
  } catch {}
  demo.value = createCallSimulation();
  seconds.value = 10;
  timer = setInterval(() => {
    if (seconds.value !== null) {
      if (seconds.value <= 1) launch();
      else seconds.value--;
    }
  }, 1000);
}
onMounted(restart);
onBeforeUnmount(() => {
  clear();
  try {
    sessionStorage.removeItem(`amx-call:assurance:${demo.value.contact.id}`);
  } catch {}
});
</script>
<template>
  <div class="amx-root">
    <div class="crm-shell crm-connected setter-shell compact-type call-simulation">
      <main class="amx-main">
        <header class="simulation-heading">
          <span class="simulation-icon"><Phone :size="26" /></span
          ><span>ORVIA · APERÇU INTERACTIF</span>
          <h1>Essayez votre interface d’appel.</h1>
          <p>La vraie fiche Assurance, avec des réponses simulées.</p>
        </header>
        <div class="simulation-notice" role="status">
          <ShieldCheck :size="20" />
          <p>
            <strong>Simulation uniquement.</strong> Aucun appel réel, aucun audio, aucun envoi
            d’e-mail ni écriture dans le CRM. Les saisies sont conservées en mémoire jusqu’à la
            fermeture ou au redémarrage de cet aperçu.
          </p>
        </div>
        <div class="simulation-summary">
          <h2>
            {{
              stopped
                ? 'Simulation arrêtée'
                : opened
                  ? 'Fiche d’appel ouverte'
                  : 'Explorez le parcours'
            }}
          </h2>
          <p>
            Décompte → fiche prospect → commande simulée → résultat, note, rappel, qualification et
            rendez-vous fictif.
          </p>
          <p>Les disponibilités et les rendez-vous de cet aperçu utilisent l’heure de Montréal.</p>
          <div>
            <button class="primary" :disabled="opened" @click="restart">
              <RotateCcw :size="16" />Rejouer la simulation</button
            ><a class="secondary" href="/crm">Retour au CRM</a>
          </div>
        </div>
        <CallCountdownModal
          v-if="seconds !== null"
          :seconds="seconds"
          :prospect="demo.contact.name"
          simulated
          @stop="stop"
          ><button class="primary" @click="launch">Simuler maintenant</button
          ><button class="secondary" @click="stop">
            Arrêter la simulation
          </button></CallCountdownModal
        >
        <SidePanel
          :open="opened"
          title="SIMULATION · Fiche d’appel"
          subtitle="Aucune opération réelle · données en mémoire"
          :close-disabled="busy"
          :scrollable="false"
          @request-close="editor?.close()"
        >
          <p class="simulation-banner">
            SIMULATION · Les messages « enregistré » et « réservé » concernent uniquement cet
            aperçu.
          </p>
          <AssuranceContactEditor
            v-if="opened"
            :key="demo.contact.id"
            ref="editor"
            :contact="demo.contact"
            role="setter"
            workflow="call"
            auto-call
            :request="demo.request"
            :portal="demo.portal"
            @busy="busy = $event"
            @close="opened = false"
          />
        </SidePanel>
      </main>
    </div>
  </div>
</template>
<style scoped>
.call-simulation {
  min-height: 100dvh;
  background: #f5f6fb;
}
.call-simulation > .amx-main {
  width: min(900px, 100%);
  margin: 0 auto;
  padding: 50px 24px;
}
.simulation-heading {
  text-align: center;
  display: grid;
  justify-items: center;
  gap: 14px;
}
.simulation-heading > span:nth-child(2) {
  font-size: 11px;
  letter-spacing: 1.5px;
  color: #7763b0;
}
.simulation-icon {
  display: grid;
  place-items: center;
  width: 64px;
  height: 64px;
  border-radius: 22px;
  background: #e9e2ff;
  color: #6a51c8;
}
.simulation-heading p,
.simulation-summary p {
  color: #64748b;
  line-height: 1.7;
  font-size: 13px;
  margin: 10px 0;
}
.simulation-notice {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin: 28px 0;
  padding: 18px;
  border: 1px solid #d5dfe9;
  background: #fff;
  border-radius: 14px;
  color: #475569;
}
.simulation-notice svg {
  flex-shrink: 0;
}
.simulation-notice p {
  font-size: 12px;
  line-height: 1.7;
}
.simulation-summary {
  border-radius: 18px;
  padding: 28px;
  background: white;
  border: 1px solid #e1e5ee;
}
.simulation-summary > div {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 20px;
}
.simulation-summary button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.simulation-banner {
  padding: 12px 20px;
  background: #fff2cb;
  color: #735722;
  font-size: 11px;
  line-height: 1.6;
}
</style>
