<script setup lang="ts">
import { ref } from 'vue';
import { Phone, ShieldCheck, Eye, EyeOff, LogIn, LockKeyhole } from 'lucide-vue-next';
defineProps<{ busy: boolean; error: string }>();
const emit = defineEmits<{
  submit: [value: { username: string; password: string }];
  recover: [];
}>();
// Credentials first: the portal then opens the only authorised space, or lists them.
const username = ref(''),
  password = ref(''),
  visible = ref(false);
function submit() {
  const secret = password.value;
  password.value = '';
  emit('submit', { username: username.value, password: secret });
}
</script>
<template>
  <div class="login-shell profile-login">
    <header class="login-header">
      <a class="brand" href="/crm"
        ><span class="brand-mark"><Phone :size="22" stroke-width="2.5" /></span>Orvia<span
          class="brand-dot"
          >.</span
        ></a
      ><span class="login-private"><LockKeyhole :size="15" /> Votre espace privé</span>
    </header>
    <div class="login-art route-art" aria-hidden="true">
      <svg viewBox="0 0 420 430" fill="none">
        <path
          d="M-25 363L63 350L104 297L96 240L154 191L223 185L244 146L267 133L288 139L322 126L337 69L331 28"
          stroke="#36382e"
          stroke-width="4"
          stroke-linejoin="round"
        />
        <path d="M-25 368L65 355L109 298L101 244" stroke="#36382e" stroke-width="1" />
        <g transform="rotate(-5 231 200)">
          <rect
            x="146"
            y="172"
            width="207"
            height="66"
            rx="6"
            fill="#f6f5ed"
            stroke="#36382e"
            stroke-width="2"
          />
          <path
            d="M167 194L179 205L174 207L169 218L164 216L169 206L164 204Z"
            stroke="#36382e"
            stroke-width="2"
          />
          <text
            x="191"
            y="200"
            fill="#36382e"
            font-size="11"
            font-family="monospace"
            letter-spacing="1"
          >
            LA BONNE LISTE,
          </text>
          <text
            x="191"
            y="220"
            fill="#36382e"
            font-size="11"
            font-family="monospace"
            letter-spacing="1"
          >
            LE BON CONTACT.
          </text>
        </g>
        <circle cx="330" cy="28" r="16" fill="#dd792f" />
        <path
          d="M324 28L328 32L336 23"
          stroke="#fff"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </div>
    <div class="login-art phone-art" aria-hidden="true">
      <svg viewBox="0 0 290 280" fill="none">
        <path
          d="M65 34C54 29 40 34 34 45L16 77C1 106 38 162 78 202C118 242 175 278 203 261L236 243C247 237 252 223 246 212L223 169C218 159 206 155 196 160L166 176C152 170 137 158 123 144C110 131 97 115 92 102L107 73C112 62 108 51 98 46Z"
          fill="#9380dc"
        />
        <path
          d="M174 30C211 38 238 65 246 101M176 65C195 70 208 84 212 102"
          stroke="#9380dc"
          stroke-width="14"
          stroke-linecap="round"
        /></svg
      ><span>PRÊT À FAIRE LE LIEN ?</span>
    </div>
    <div class="login-art burst-art" aria-hidden="true">
      <svg viewBox="0 0 160 120">
        <path
          d="M20 91L139 91M38 76L29 65M56 65L43 39M77 59L73 22M99 61L109 29M118 73L137 51"
          fill="none"
          stroke="#bac34c"
          stroke-width="12"
        />
      </svg>
    </div>
    <div class="login-art star-art" aria-hidden="true">
      <svg viewBox="0 0 100 100">
        <path
          d="M50 5L60 35L89 25L72 50L94 68L63 66L53 97L43 69L12 81L28 55L4 36L37 38Z"
          fill="#ef8739"
        />
      </svg>
    </div>
    <div class="login-art bottom-route-art" aria-hidden="true">
      <svg viewBox="0 0 400 260" fill="none">
        <path
          d="M44 174L23 196L29 218L65 209L96 180L152 239L275 218L256 106L277 78L386 91L416 61"
          stroke="#36382e"
          stroke-width="4"
          stroke-linejoin="round"
        />
        <g transform="rotate(4 270 90)">
          <rect
            x="185"
            y="54"
            width="200"
            height="45"
            rx="23"
            fill="#f6f5ed"
            stroke="#36382e"
            stroke-width="2"
          />
          <circle cx="209" cy="76" r="8" stroke="#36382e" stroke-width="2" />
          <path d="M204 76L208 80L214 73" stroke="#36382e" stroke-width="2" />
          <text x="227" y="80" fill="#36382e" font-family="monospace" font-size="10">
            DES DONNÉES PLUS FIABLES
          </text>
        </g>
        <circle cx="44" cy="174" r="16" fill="#53661c" />
        <path d="M39 174L43 178L50 170" stroke="#fff" stroke-width="2" />
      </svg>
    </div>

    <main class="login-main">
      <div class="login-form-wrap">
        <span class="welcome-icon"><Phone :size="23" /></span>
        <h2>Heureux de vous revoir !</h2>
        <p>Connectez-vous avec vos identifiants : votre espace s’ouvre ensuite automatiquement.</p>
        <form @submit.prevent="submit">
          <label for="crm-username">Votre identifiant</label
          ><input
            id="crm-username"
            v-model="username"
            autocomplete="username"
            placeholder="Votre identifiant"
            required
            :disabled="busy"
          />
          <div class="label-line">
            <label for="crm-password">Mot de passe</label
            ><button
              type="button"
              class="text-button"
              :disabled="busy"
              @click="
                password = '';
                emit('recover');
              "
            >
              Mot de passe oublié ?
            </button>
          </div>
          <div class="password-input">
            <input
              id="crm-password"
              v-model="password"
              :type="visible ? 'text' : 'password'"
              autocomplete="current-password"
              placeholder="Saisissez votre mot de passe"
              required
              :disabled="busy"
            /><button
              type="button"
              :aria-label="visible ? 'Masquer le mot de passe' : 'Afficher le mot de passe'"
              @click="visible = !visible"
            >
              <EyeOff v-if="visible" :size="19" /><Eye v-else :size="19" />
            </button>
          </div>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <button class="primary login-submit" :disabled="busy">
            <LogIn :size="20" />{{ busy ? 'Connexion…' : 'Se connecter' }}
          </button>
        </form>
        <div class="access-note">
          <LockKeyhole :size="15" />
          <p>Seuls les espaces autorisés sur votre compte sont accessibles.</p>
        </div>
      </div>
    </main>
    <footer class="login-footer">
      <span>© {{ new Date().getFullYear() }} Orvia</span
      ><span><ShieldCheck :size="13" />Vos données restent dans votre espace privé.</span>
    </footer>
  </div>
</template>
<style scoped>
.profile-login {
  min-height: 100dvh;
}
.profile-login .login-main {
  min-height: calc(100dvh - 170px);
}
.profile-login .login-form-wrap {
  max-width: 470px;
}
.profile-login .access-note {
  margin-top: 28px;
}
.profile-login .login-submit {
  background: #53661c;
  border-color: #53661c;
}
.profile-login .login-form-wrap form {
  text-align: left;
}
.profile-login .login-form-wrap input {
  width: 100%;
  box-sizing: border-box;
}
@media (max-width: 600px) {
  .profile-login .login-main {
    padding-top: 40px;
    padding-bottom: 40px;
  }
}
</style>
