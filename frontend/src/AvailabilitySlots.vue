<script setup lang="ts">
// Day grid of bookable slots. Busy intervals come from the CRM; external calendars are still
// checked by the server when the booking is confirmed.
import { ref, computed, watch } from 'vue';
import { bookingInterval } from './booking-time';

type Busy = { starts_at: string; ends_at: string };
const props = defineProps<{
  modelValue: string;
  zone: string;
  duration: number;
  disabled?: boolean;
  label: string;
  note: string;
  // Returns busy intervals between two explicit instants; `key` reloads when it changes.
  load: (start: string, end: string) => Promise<Busy[]>;
  loadKey: string;
  fullDay?: boolean;
}>();
const emit = defineEmits<{ 'update:modelValue': [value: string] }>();
const FIRST_HOUR = 8,
  LAST_HOUR = 20,
  STEP = 30;
function dayIn(date: Date, timeZone: string) {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date);
}
function shiftDay(day: string, delta: number) {
  const date = new Date(day + 'T12:00:00Z');
  date.setUTCDate(date.getUTCDate() + delta);
  return date.toISOString().slice(0, 10);
}
const day = ref(dayIn(new Date(), props.zone)),
  busy = ref<Busy[]>([]),
  loading = ref(false),
  error = ref('');
const today = computed(() => dayIn(new Date(), props.zone));
const title = computed(() =>
  new Intl.DateTimeFormat('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    timeZone: 'UTC',
  }).format(new Date(day.value + 'T12:00:00Z')),
);
const slots = computed(() => {
  const now = Date.now(),
    result: { local: string; label: string; state: 'free' | 'busy' | 'past' }[] = [];
  for (
    let minutes = (props.fullDay ? 0 : FIRST_HOUR) * 60;
    minutes < (props.fullDay ? 24 : LAST_HOUR) * 60;
    minutes += STEP
  ) {
    const label = `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
    const local = `${day.value}T${label}`;
    let interval;
    try {
      interval = bookingInterval(local, props.zone, props.duration);
    } catch {
      continue; // Nonexistent or repeated time at a daylight-saving change.
    }
    const from = Date.parse(interval.starts_at),
      to = Date.parse(interval.ends_at);
    const state =
      from < now
        ? 'past'
        : busy.value.some((row) => Date.parse(row.starts_at) < to && Date.parse(row.ends_at) > from)
          ? 'busy'
          : 'free';
    result.push({ local, label, state });
  }
  return result;
});
let version = 0;
async function refresh() {
  const current = ++version;
  loading.value = true;
  error.value = '';
  try {
    const from = bookingInterval(`${day.value}T00:00`, props.zone, 15).starts_at,
      to = bookingInterval(`${shiftDay(day.value, 1)}T00:00`, props.zone, 15).starts_at;
    const rows = await props.load(from, to);
    if (current === version) busy.value = rows;
  } catch (e: any) {
    if (current === version) {
      busy.value = [];
      error.value = e.message;
    }
  } finally {
    if (current === version) loading.value = false;
  }
}
watch([day, () => props.zone, () => props.loadKey], () => void refresh(), { immediate: true });
</script>

<template>
  <section class="availability-slots" :aria-label="label">
    <header>
      <button
        type="button"
        class="secondary"
        aria-label="Jour précédent"
        :disabled="day <= today"
        @click="day = shiftDay(day, -1)"
      >
        ‹</button
      ><strong>{{ title }}</strong
      ><button
        type="button"
        class="secondary"
        aria-label="Jour suivant"
        @click="day = shiftDay(day, 1)"
      >
        ›
      </button>
    </header>
    <p v-if="error" role="alert" class="error">
      {{ error }} <button type="button" class="secondary" @click="refresh">Réessayer</button>
    </p>
    <p v-else-if="loading" role="status" class="subtle">Chargement des disponibilités…</p>
    <div v-else class="slot-grid">
      <button
        v-for="slot in slots"
        :key="slot.local"
        type="button"
        :class="[slot.state, { selected: modelValue === slot.local }]"
        :disabled="slot.state !== 'free' || disabled"
        :aria-pressed="modelValue === slot.local"
        :title="
          slot.state === 'busy'
            ? 'Créneau indisponible (horaire fermé ou rendez-vous existant)'
            : undefined
        "
        @click="emit('update:modelValue', slot.local)"
      >
        {{ slot.label }}
      </button>
    </div>
    <small
      >Créneaux de {{ fullDay ? 0 : FIRST_HOUR }} h à {{ fullDay ? 24 : LAST_HOUR }} h selon le CRM.
      {{ note }}</small
    >
  </section>
</template>

<style scoped>
.availability-slots {
  display: grid;
  gap: 10px;
  margin: 4px 0 12px;
}
.availability-slots header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.availability-slots header strong {
  text-transform: capitalize;
}
.slot-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(72px, 1fr));
  gap: 8px;
}
.slot-grid button {
  border: 1px solid #cfd8e3;
  border-radius: 8px;
  background: white;
  padding: 8px 0;
  font-variant-numeric: tabular-nums;
  cursor: pointer;
}
.slot-grid button.busy {
  background: #f1f3f6;
  color: #9aa5b4;
  text-decoration: line-through;
  cursor: not-allowed;
}
.slot-grid button.past {
  opacity: 0.45;
  cursor: not-allowed;
}
.slot-grid button.selected {
  background: #1f5fa8;
  border-color: #1f5fa8;
  color: white;
}
.availability-slots small {
  color: #6b7686;
}
</style>
