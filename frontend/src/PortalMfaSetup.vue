<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { LockKeyhole, ShieldCheck } from 'lucide-vue-next';

const props = defineProps<{ portal: (path: string, body?: any) => Promise<any> }>();
const emit = defineEmits<{ complete: [] }>();
const loading = ref(false),
  error = ref(''),
  qr = ref(''),
  uri = ref(''),
  code = ref(''),
  backupCodes = ref<string[]>([]);
const secret = computed(() => {
  try {
    return new URL(uri.value).searchParams.get('secret') || '';
  } catch {
    return '';
  }
});
async function start() {
  loading.value = true;
  error.value = '';
  try {
    const result = await props.portal('mfa/', { action: 'enroll' });
    qr.value = result.qr;
    uri.value = result.uri;
  } catch (reason: any) {
    error.value = reason.message;
  } finally {
    loading.value = false;
  }
}
async function confirm() {
  loading.value = true;
  error.value = '';
  try {
    const result = await props.portal('mfa/', { action: 'confirm', code: code.value.trim() });
    backupCodes.value = result.backup_codes || [];
  } catch (reason: any) {
    error.value = reason.message;
  } finally {
    loading.value = false;
  }
}
function downloadCodes() {
  const file = new Blob(
    [
      'ORVIA — Codes de secours MFA\nConservez ce fichier dans un endroit sûr. Chaque code ne fonctionne qu’une fois.\n\n',
      backupCodes.value.join('\n'),
      '\n',
    ],
    { type: 'text/plain;charset=utf-8' },
  );
  const url = URL.createObjectURL(file);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'orvia-codes-secours-mfa.txt';
  link.click();
  URL.revokeObjectURL(url);
}
onMounted(start);
</script>

<template>
  <main class="portal-mfa-page">
    <section class="portal-mfa-card" aria-labelledby="portal-mfa-title">
      <span class="portal-mfa-icon"><ShieldCheck :size="24" /></span>
      <p class="portal-mfa-eyebrow">SÉCURITÉ DU COMPTE ADMINISTRATEUR</p>
      <h1 id="portal-mfa-title">Activez la double authentification</h1>
      <p class="portal-mfa-lead">
        Scannez le QR code avec une application d’authentification, puis saisissez le code à six
        chiffres. Cette étape est nécessaire pour ouvrir l’espace administrateur.
      </p>

      <template v-if="backupCodes.length">
        <div class="portal-mfa-success" role="status">
          <ShieldCheck :size="18" /> La MFA est activée. Enregistrez maintenant vos codes de
          secours.
        </div>
        <p class="portal-mfa-lead">
          Chaque code fonctionne une seule fois si vous perdez l’accès à votre application. ORVIA ne
          les affichera plus après cette étape.
        </p>
        <ol class="portal-mfa-codes">
          <li v-for="backup in backupCodes" :key="backup">{{ backup }}</li>
        </ol>
        <button type="button" class="secondary" @click="downloadCodes">
          Télécharger les codes
        </button>
        <button class="primary portal-mfa-continue" @click="emit('complete')">
          J’ai enregistré mes codes — continuer
        </button>
      </template>

      <template v-else>
        <div v-if="loading && !qr" class="portal-mfa-loading" role="status">Préparation…</div>
        <div v-else class="portal-mfa-enrollment">
          <img v-if="qr" class="portal-mfa-qr" :src="qr" alt="QR code de configuration MFA" />
          <div class="portal-mfa-manual">
            <strong>Configuration manuelle</strong>
            <p>Si le scan ne fonctionne pas, saisissez cette clé dans votre application :</p>
            <code>{{ secret }}</code>
          </div>
          <form @submit.prevent="confirm">
            <label for="portal-mfa-code">Code de l’application</label>
            <input
              id="portal-mfa-code"
              v-model="code"
              autocomplete="one-time-code"
              inputmode="numeric"
              pattern="[0-9]{6}"
              maxlength="6"
              placeholder="000000"
              required
            />
            <p v-if="error" class="portal-mfa-error" role="alert">{{ error }}</p>
            <button class="primary" :disabled="loading || code.trim().length !== 6">
              <LockKeyhole :size="17" />{{ loading ? 'Vérification…' : 'Activer la MFA' }}
            </button>
          </form>
        </div>
      </template>
      <p v-if="error && backupCodes.length" class="portal-mfa-error" role="alert">{{ error }}</p>
      <p class="portal-mfa-footnote">Ne communiquez jamais vos codes à une autre personne.</p>
    </section>
  </main>
</template>

<style scoped>
.portal-mfa-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 28px 18px;
  background: #f6f5ed;
}
.portal-mfa-card {
  width: min(100%, 560px);
  box-sizing: border-box;
  padding: 34px;
  border: 1px solid #e3e3d8;
  border-radius: 22px;
  background: #fff;
  box-shadow: 0 16px 46px #20271e12;
}
.portal-mfa-icon {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  border-radius: 15px;
  background: #edf0dc;
  color: #53661c;
}
.portal-mfa-eyebrow {
  margin: 22px 0 8px;
  color: #69715a;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
}
.portal-mfa-card h1 {
  margin: 0;
  color: #20271e;
  font-size: clamp(23px, 5vw, 30px);
  line-height: 1.2;
}
.portal-mfa-lead {
  color: #62685d;
  line-height: 1.6;
}
.portal-mfa-enrollment {
  display: grid;
  justify-items: center;
  gap: 18px;
  margin-top: 24px;
}
.portal-mfa-qr {
  width: 210px;
  height: 210px;
  padding: 10px;
  border: 1px solid #e3e3d8;
  border-radius: 12px;
  background: white;
}
.portal-mfa-manual {
  width: 100%;
  padding: 15px;
  box-sizing: border-box;
  border-radius: 12px;
  background: #f8f8f4;
}
.portal-mfa-manual p {
  margin: 7px 0;
  color: #62685d;
  line-height: 1.5;
}
.portal-mfa-manual code {
  overflow-wrap: anywhere;
  font-size: 13px;
}
.portal-mfa-enrollment form {
  display: grid;
  gap: 10px;
  width: 100%;
}
.portal-mfa-enrollment input {
  box-sizing: border-box;
  width: 100%;
  padding: 12px;
  border: 1px solid #c9cebd;
  border-radius: 10px;
  font: inherit;
  font-size: 20px;
  letter-spacing: 0.2em;
  text-align: center;
}
.portal-mfa-enrollment button,
.portal-mfa-continue {
  min-height: 46px;
  display: inline-flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
  width: 100%;
  margin-top: 8px;
}
.portal-mfa-codes {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 14px;
  width: 100%;
  padding: 16px 16px 16px 38px;
  box-sizing: border-box;
  border: 1px solid #e3e3d8;
  border-radius: 12px;
  background: #f8f8f4;
  font-family: ui-monospace, monospace;
}
.portal-mfa-success {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 20px 0;
  color: #36520d;
  font-weight: 700;
}
.portal-mfa-error {
  color: #a22e2e;
}
.portal-mfa-loading,
.portal-mfa-footnote {
  margin-top: 22px;
  color: #69715a;
  font-size: 13px;
}
@media (max-width: 480px) {
  .portal-mfa-card {
    padding: 24px 19px;
  }
}
</style>
