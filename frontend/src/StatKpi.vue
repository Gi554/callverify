<script setup lang="ts">
// Dashboard indicator: value, trend against the previous period and a daily sparkline.
import { computed } from 'vue';
const props = defineProps<{
  label: string;
  value: string | number;
  // Relative change in %, or absolute change in points when `points` is set.
  trend?: number | null;
  points?: boolean;
  // A rise is bad news (e.g. missing reports): colours are inverted.
  inverse?: boolean;
  series?: number[];
  hint?: string;
}>();
const tone = computed(() => {
  if (props.trend == null || props.trend === 0) return 'flat';
  return props.trend > 0 !== !!props.inverse ? 'good' : 'bad';
});
const badge = computed(() => {
  if (props.trend == null) return '';
  const sign = props.trend > 0 ? '+' : '';
  const number = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 }).format(props.trend);
  return `${sign}${number}${props.points ? ' pt' : ' %'}`;
});
const path = computed(() => {
  const values = props.series || [];
  if (values.length < 2) return '';
  const max = Math.max(...values),
    min = Math.min(...values),
    span = max - min || 1;
  return values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * 100;
      const y = 26 - ((value - min) / span) * 22;
      return `${index ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
});
</script>

<template>
  <div class="kpi-card">
    <header>
      <span>{{ label }}</span>
      <span
        v-if="badge"
        :class="['kpi-trend', tone]"
        :title="'Par rapport à la période précédente de même durée'"
        >{{ badge }}</span
      >
    </header>
    <div class="kpi-body">
      <strong>{{ value }}</strong>
      <svg v-if="path" :class="['kpi-spark', tone]" viewBox="0 0 100 30" aria-hidden="true">
        <path :d="path" fill="none" vector-effect="non-scaling-stroke" />
      </svg>
    </div>
    <p v-if="hint">{{ hint }}</p>
  </div>
</template>

<style scoped>
.kpi-card {
  margin: 0;
  display: grid;
  gap: 10px;
  align-content: start;
  min-width: 0;
  padding: 16px 18px;
  border: 1px solid #e6e9f0;
  border-radius: 14px;
  background: white;
}
.kpi-card header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: #475467;
  font-size: 13px;
  font-weight: 600;
}
.kpi-trend {
  padding: 2px 7px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}
.kpi-trend.good {
  background: #e3f7ec;
  color: #12804a;
}
.kpi-trend.bad {
  background: #fde8e8;
  color: #c0362c;
}
.kpi-trend.flat {
  background: #f0f2f5;
  color: #5b6b82;
}
.kpi-body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.kpi-body strong {
  color: #101828;
  font-size: 26px;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.kpi-spark {
  flex: 0 1 96px;
  height: 32px;
  min-width: 56px;
}
.kpi-spark path {
  stroke-width: 2;
  stroke-linejoin: round;
  stroke-linecap: round;
  stroke: #2f6fed;
}
.kpi-spark.good path {
  stroke: #12a05c;
}
.kpi-spark.bad path {
  stroke: #e0483d;
}
.kpi-card p {
  margin: 0;
  color: #667085;
  font-size: 12px;
}
</style>
