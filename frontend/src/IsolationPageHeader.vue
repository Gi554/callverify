<script setup lang="ts">
import { RefreshCw } from 'lucide-vue-next';
withDefaults(defineProps<{ title: string; subtitle: string; eyebrow?: string; busy?: boolean }>(), {
  eyebrow: 'MON ESPACE · ISOLATION',
});
defineEmits<{ refresh: [] }>();
</script>
<template>
  <header class="iso-page-heading">
    <div class="iso-heading-copy">
      <span class="iso-eyebrow"><span></span>{{ eyebrow }}</span>
      <h1>{{ title }}<span class="iso-title-dot">.</span></h1>
      <p>{{ subtitle }}</p>
    </div>
    <div class="iso-heading-actions">
      <slot name="actions" /><button
        class="secondary iso-refresh"
        aria-label="Actualiser"
        title="Actualiser"
        :disabled="busy"
        @click="$emit('refresh')"
      >
        <RefreshCw :size="15" :class="{ 'iso-spinning': busy }" /><span>Actualiser</span>
      </button>
    </div>
  </header>
</template>
