<script setup lang="ts">
// Ring chart of mutually exclusive outcomes, with a central figure and a legend.
import { computed } from 'vue';
const props = defineProps<{
  title: string;
  center: string;
  caption: string;
  segments: { label: string; value: number; color: string }[];
}>();
const total = computed(() => props.segments.reduce((sum, item) => sum + item.value, 0));
const RADIUS = 52,
  LENGTH = 2 * Math.PI * RADIUS;
const arcs = computed(() => {
  let offset = 0;
  return props.segments
    .filter((item) => item.value > 0)
    .map((item) => {
      const length = (item.value / total.value) * LENGTH;
      const arc = { ...item, dash: `${length} ${LENGTH - length}`, offset: -offset };
      offset += length;
      return arc;
    });
});
const share = (value: number) =>
  total.value ? Math.round((100 * value) / total.value) + ' %' : '—';
</script>

<template>
  <div class="donut-card">
    <h3>{{ title }}</h3>
    <div class="donut">
      <svg viewBox="0 0 128 128" role="img" :aria-label="`${title} : ${center} ${caption}`">
        <circle cx="64" cy="64" :r="RADIUS" class="donut-track" />
        <circle
          v-for="arc in arcs"
          :key="arc.label"
          cx="64"
          cy="64"
          :r="RADIUS"
          class="donut-arc"
          :stroke="arc.color"
          :stroke-dasharray="arc.dash"
          :stroke-dashoffset="arc.offset"
        />
      </svg>
      <div class="donut-center">
        <strong>{{ center }}</strong
        ><span>{{ caption }}</span>
      </div>
    </div>
    <ul>
      <li v-for="item in segments" :key="item.label">
        <i :style="{ background: item.color }"></i>{{ item.label
        }}<b>{{ item.value }} · {{ share(item.value) }}</b>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.donut-card {
  margin: 0;
  display: grid;
  gap: 14px;
  align-content: start;
  padding: 18px;
  border: 1px solid #e6e9f0;
  border-radius: 14px;
  background: white;
}
.donut-card h3 {
  margin: 0;
  font-size: 15px;
  color: #101828;
}
.donut {
  position: relative;
  width: min(170px, 100%);
  margin: 0 auto;
}
.donut svg {
  display: block;
  width: 100%;
  transform: rotate(-90deg);
}
.donut-track,
.donut-arc {
  fill: none;
  stroke-width: 14;
}
.donut-track {
  stroke: #eef1f6;
}
.donut-center {
  position: absolute;
  inset: 0;
  display: grid;
  place-content: center;
  text-align: center;
}
.donut-center strong {
  font-size: 24px;
  color: #2f6fed;
}
.donut-center span {
  color: #667085;
  font-size: 11px;
}
.donut-card ul {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: 12px;
  color: #475467;
}
.donut-card li {
  display: flex;
  align-items: center;
  gap: 8px;
}
.donut-card li i {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  flex: none;
}
.donut-card li b {
  margin-left: auto;
  color: #101828;
  font-weight: 600;
  white-space: nowrap;
}
</style>
