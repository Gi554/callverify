<script setup lang="ts">
// Grouped bars per day, week or month from a zero-filled daily series.
import { ref, computed, watch } from 'vue';
const props = defineProps<{
  title: string;
  days: Record<string, any>[];
  series: { key: string; label: string; color: string }[];
}>();
type Grain = 'day' | 'week' | 'month';
const grains: [Grain, string][] = [
  ['day', 'Jour'],
  ['week', 'Semaine'],
  ['month', 'Mois'],
];
const auto = (): Grain =>
  props.days.length <= 14 ? 'day' : props.days.length <= 92 ? 'week' : 'month';
const grain = ref<Grain>(auto());
watch(
  () => props.days.length,
  () => (grain.value = auto()),
);
const active = ref<number | null>(null);
const date = (day: string) => new Date(day + 'T12:00:00Z');
const format = (options: Intl.DateTimeFormatOptions, day: string) =>
  new Intl.DateTimeFormat('fr-FR', { ...options, timeZone: 'UTC' }).format(date(day));
function bucketOf(day: string) {
  if (grain.value === 'day') return day;
  if (grain.value === 'month') return day.slice(0, 7);
  const value = date(day);
  value.setUTCDate(value.getUTCDate() - ((value.getUTCDay() + 6) % 7));
  return value.toISOString().slice(0, 10);
}
const buckets = computed<Record<string, any>[]>(() => {
  const groups = new Map<string, Record<string, any>>();
  for (const row of props.days) {
    const key = bucketOf(String(row.day));
    const group = groups.get(key) || { key, first: String(row.day) };
    for (const item of props.series) group[item.key] = (group[item.key] || 0) + row[item.key];
    groups.set(key, group);
  }
  return [...groups.values()].map((group) => ({
    ...group,
    label:
      grain.value === 'day'
        ? format({ weekday: 'short', day: 'numeric' }, group.first)
        : grain.value === 'week'
          ? 'Sem. ' + format({ day: 'numeric', month: 'numeric' }, group.key)
          : format({ month: 'short', year: '2-digit' }, group.key + '-01'),
  }));
});
const max = computed(() =>
  Math.max(1, ...buckets.value.flatMap((group) => props.series.map((item) => group[item.key]))),
);
const height = (value: number) => `${Math.max(value ? 4 : 0, (value / max.value) * 100)}%`;
</script>

<template>
  <div class="bars-card">
    <header>
      <div>
        <h3>{{ title }}</h3>
        <ul class="bars-legend">
          <li v-for="item in series" :key="item.key">
            <i :style="{ background: item.color }"></i>{{ item.label }}
          </li>
        </ul>
      </div>
      <div class="bars-grain" role="group" aria-label="Regroupement">
        <button
          v-for="[key, label] in grains"
          :key="key"
          type="button"
          :class="{ 'is-active': grain === key }"
          :aria-pressed="grain === key"
          @click="
            grain = key;
            active = null;
          "
        >
          {{ label }}
        </button>
      </div>
    </header>
    <p v-if="!buckets.length" class="bars-empty">Aucune donnée quotidienne pour cette période.</p>
    <div v-else class="bars-scroll">
      <div class="bars" :style="{ minWidth: buckets.length * 44 + 'px' }">
        <button
          v-for="(group, index) in buckets"
          :key="group.key"
          type="button"
          class="bars-group"
          :class="{ 'is-active': active === index }"
          :aria-label="
            group.label +
            ' : ' +
            series.map((item) => `${item.label} ${group[item.key]}`).join(', ')
          "
          @mouseenter="active = index"
          @mouseleave="active = null"
          @focus="active = index"
          @blur="active = null"
        >
          <span v-if="active === index" class="bars-tip">
            <b v-for="item in series" :key="item.key">{{ group[item.key] }} {{ item.label }}</b>
          </span>
          <span class="bars-columns">
            <span
              v-for="item in series"
              :key="item.key"
              class="bar"
              :style="{ height: height(group[item.key]), background: item.color }"
            ></span>
          </span>
          <small>{{ group.label }}</small>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bars-card {
  margin: 0;
  display: grid;
  gap: 14px;
  min-width: 0;
  padding: 18px;
  border: 1px solid #e6e9f0;
  border-radius: 14px;
  background: white;
}
.bars-card header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.bars-card h3 {
  margin: 0 0 6px;
  font-size: 15px;
  color: #101828;
}
.bars-legend {
  display: flex;
  gap: 14px;
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: 12px;
  color: #475467;
}
.bars-legend li {
  display: flex;
  align-items: center;
  gap: 6px;
}
.bars-legend i {
  width: 10px;
  height: 10px;
  border-radius: 3px;
}
.bars-grain {
  display: inline-flex;
  gap: 2px;
}
.bars-grain button {
  border: 0;
  background: none;
  padding: 4px 8px;
  min-height: 0;
  border-radius: 6px;
  color: #98a2b3;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.bars-grain button.is-active {
  color: #101828;
  background: #f0f3f9;
}
.bars-empty {
  margin: 0;
  padding: 40px 0;
  color: #98a2b3;
  font-size: 13px;
  text-align: center;
}
.bars-scroll {
  overflow-x: auto;
}
.bars {
  display: flex;
  align-items: stretch;
  gap: 6px;
  height: 220px;
  padding-top: 34px;
}
.bars-group {
  position: relative;
  display: grid;
  grid-template-rows: 1fr auto;
  flex: 1 1 0;
  min-width: 38px;
  gap: 6px;
  padding: 0;
  min-height: 0;
  border: 0;
  border-radius: 8px;
  background: none;
  cursor: default;
}
.bars-group.is-active {
  background: #f5f7fb;
}
.bars-columns {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 4px;
  height: 100%;
}
.bar {
  width: min(16px, 40%);
  border-radius: 4px 4px 0 0;
}
.bars-group small {
  color: #667085;
  font-size: 11px;
  white-space: nowrap;
  text-align: center;
}
.bars-group.is-active small {
  color: #101828;
  font-weight: 700;
}
.bars-tip {
  position: absolute;
  top: 0;
  left: 50%;
  z-index: 1;
  display: grid;
  gap: 2px;
  padding: 5px 8px;
  border-radius: 6px;
  background: #1d2939;
  color: white;
  font-size: 11px;
  white-space: nowrap;
  transform: translate(-50%, -100%);
}
.bars-tip b {
  font-weight: 600;
}
</style>
