<script setup lang="ts">
import { ArrowUpRight, MapPin, Clock3, Phone, UserRound } from 'lucide-vue-next';
import {
  visitName,
  initials,
  visitStatus,
  visitTone,
  visitDay,
  visitMonth,
  visitTime,
} from './isolation-visit-display';
defineProps<{ visit: any; busy?: boolean; actionLabel?: string }>();
defineEmits<{ open: [] }>();
</script>
<template>
  <article class="iso-visit-card" :class="'tone-' + visitTone(visit)">
    <div class="iso-visit-top">
      <span class="iso-avatar">{{ initials(visitName(visit)) }}</span
      ><span class="iso-status" :class="visitTone(visit)"
        ><span></span>{{ visitStatus(visit) }}</span
      >
    </div>
    <h3>{{ visitName(visit) }}</h3>
    <p class="iso-card-phone">
      <Phone :size="13" />{{
        visit.c2_snapshot?.fields?.phone || visit.prospect?.phone || 'Téléphone non renseigné'
      }}
    </p>
    <div class="iso-visit-slot">
      <span class="iso-date-tile"
        ><strong>{{ visitDay(visit.starts_at) }}</strong
        ><small>{{ visitMonth(visit.starts_at) }}</small></span
      >
      <div>
        <strong
          ><Clock3 :size="14" />{{ visitTime(visit.starts_at)
          }}<template v-if="visit.ends_at"> – {{ visitTime(visit.ends_at) }}</template></strong
        ><small>Heure du Québec</small>
      </div>
    </div>
    <p class="iso-card-address">
      <MapPin :size="15" /><span
        >{{ visit.c2_snapshot?.fields?.address || 'Adresse à consulter dans la fiche'
        }}<small>{{
          [visit.c2_snapshot?.fields?.city, visit.c2_snapshot?.fields?.postal_code]
            .filter(Boolean)
            .join(' · ')
        }}</small></span
      >
    </p>
    <div class="iso-visit-people">
      <span
        ><UserRound :size="13" />{{ visit.client?.name || 'Suivi par le client Isolation' }}</span
      ><small>Setter · {{ visit.original_setter?.name || 'Non renseigné' }}</small>
    </div>
    <button class="iso-card-open" :disabled="busy" @click="$emit('open')">
      {{ actionLabel || 'Ouvrir le rendez-vous' }}<ArrowUpRight :size="17" />
    </button>
  </article>
</template>
