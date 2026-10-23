<script setup lang="ts">
// Downloads the visible prospects (current filters, all pages) as CSV or Excel.
import { ref } from 'vue';
import { Download } from 'lucide-vue-next';
const props = defineProps<{
  request: (path: string, body?: any, method?: string) => Promise<any>;
  path: string;
  filters?: Record<string, string>;
  label?: string;
}>();
const busy = ref(''),
  error = ref('');
async function download(file: 'csv' | 'xlsx') {
  busy.value = file;
  error.value = '';
  try {
    const query = new URLSearchParams({ file });
    for (const [key, value] of Object.entries(props.filters || {}))
      if (value) query.set(key, value);
    const blob = await props.request(`${props.path}?${query}`);
    const url = URL.createObjectURL(blob);
    try {
      const link = document.createElement('a');
      link.href = url;
      link.download = `prospects.${file}`;
      link.click();
    } finally {
      URL.revokeObjectURL(url);
    }
  } catch (e: any) {
    error.value = e.message;
  } finally {
    busy.value = '';
  }
}
</script>

<template>
  <div class="prospect-export" role="group" :aria-label="label || 'Exporter les prospects'">
    <span class="prospect-export-label"><Download :size="15" />{{ label || 'Exporter' }}</span
    ><button
      type="button"
      class="secondary"
      :disabled="!!busy"
      title="Fichier CSV (séparateur point-virgule)"
      @click="download('csv')"
    >
      {{ busy === 'csv' ? 'Export…' : 'CSV' }}</button
    ><button
      type="button"
      class="secondary"
      :disabled="!!busy"
      title="Classeur Excel (.xlsx)"
      @click="download('xlsx')"
    >
      {{ busy === 'xlsx' ? 'Export…' : 'Excel' }}
    </button>
    <p v-if="error" role="alert" class="prospect-export-error">{{ error }}</p>
  </div>
</template>

<style scoped>
.prospect-export {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.prospect-export-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #475467;
}
.prospect-export button {
  min-height: 36px;
  padding: 0 12px;
}
.prospect-export-error {
  flex-basis: 100%;
  margin: 0;
  color: #b42318;
  font-size: 13px;
}
</style>
