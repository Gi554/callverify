<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, useId } from 'vue';
import { PhoneForwarded } from 'lucide-vue-next';
defineProps<{ seconds: number; prospect?: string; simulated?: boolean }>();
const emit = defineEmits<{ stop: [] }>();
const dialog = ref<HTMLDialogElement | null>(null);
const titleId = useId();
onMounted(() => dialog.value?.showModal());
onBeforeUnmount(() => dialog.value?.close());
</script>
<template>
  <dialog
    ref="dialog"
    class="call-countdown-modal"
    :aria-labelledby="titleId"
    @cancel.prevent="emit('stop')"
    @click="$event.target === dialog && emit('stop')"
  >
    <span class="countdown-icon"><PhoneForwarded :size="26" /></span>
    <p class="countdown-eyebrow">
      {{ simulated ? 'SIMULATION · AUCUN APPEL RÉEL' : 'SESSION D’APPELS' }}
    </p>
    <h2 :id="titleId">Le prochain échange arrive.</h2>
    <p v-if="prospect" class="countdown-prospect">{{ prospect }}</p>
    <p class="countdown-counter">
      Prochain appel dans <strong>{{ seconds }}</strong> s
    </p>
    <p class="countdown-help">
      Laissez cette fenêtre ouverte : à zéro, l’appel démarre automatiquement après les contrôles.
      Échap ou un clic à l’extérieur arrête la session.
    </p>
    <div class="countdown-actions"><slot /></div>
  </dialog>
</template>
<style scoped>
.call-countdown-modal {
  width: min(480px, calc(100vw - 32px));
  max-height: calc(100dvh - 40px);
  overflow: auto;
  padding: 32px;
  border: 1px solid #e0dcf0;
  border-radius: 24px;
  background: #fff;
  color: #243248;
  text-align: center;
  box-shadow: 0 25px 90px #17283c30;
}
.call-countdown-modal::backdrop {
  background: #14223873;
  backdrop-filter: blur(4px);
}
.countdown-icon {
  display: grid;
  place-items: center;
  width: 58px;
  height: 58px;
  margin: 0 auto 20px;
  border-radius: 18px;
  color: #6955d8;
  background: #eee9ff;
}
.countdown-eyebrow {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1.5px;
  color: #76688f;
}
.call-countdown-modal h2 {
  font-size: 23px;
  margin: 12px 0;
}
.countdown-prospect {
  font-size: 14px;
  color: #66738b;
  overflow-wrap: anywhere;
}
.countdown-counter {
  display: grid;
  justify-items: center;
  gap: 5px;
  margin: 22px 0;
  font-size: 13px;
  color: #66738b;
}
.countdown-counter strong {
  display: grid;
  place-items: center;
  width: 94px;
  height: 94px;
  border: 5px solid #e4ddff;
  border-radius: 50%;
  background: #f6f3ff;
  font-size: 40px;
  color: #6350ca;
  font-variant-numeric: tabular-nums;
}
.countdown-help {
  font-size: 12px;
  line-height: 1.7;
  color: #66738b;
}
.countdown-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  margin-top: 24px;
}
.call-countdown-modal :deep(button) {
  min-height: 42px;
}
@media (max-width: 480px) {
  .call-countdown-modal {
    padding: 25px 20px;
  }
}
</style>
