<script setup lang="ts">
import { computed } from 'vue'
import type { BackendStatus } from '../types'

const props = defineProps<{ backend: BackendStatus }>()

const errorRate = computed(() => {
  if (props.backend.requests === 0) return 0
  return (props.backend.errors / props.backend.requests) * 100
})

const transportIcon = computed(() => {
  const t = props.backend.transport.toLowerCase()
  if (t.includes('http')) return 'http'
  if (t.includes('ws')) return 'ws'
  if (t.includes('stdio')) return 'stdio'
  if (t.includes('sse')) return 'sse'
  return 'generic'
})

function fmtMs(n: number) {
  if (n < 1) return n.toFixed(2)
  if (n < 10) return n.toFixed(1)
  return n.toFixed(0)
}
</script>

<template>
  <div
    class="card"
    :class="[`health-${backend.health}`, { disabled: !backend.enabled }]"
  >
    <!-- Gradient border via pseudo-element -->
    <div class="card-inner">
      <header class="card-head">
        <div class="title-row">
          <span class="status-dot" :class="`s-${backend.health}`">
            <span class="ring"></span>
          </span>
          <h3 class="name" :title="backend.name">{{ backend.name }}</h3>
        </div>
        <span class="health-tag" :class="`tag-${backend.health}`">{{ backend.health }}</span>
      </header>

      <div class="meta">
        <span class="chip">
          <svg v-if="transportIcon === 'http'" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
          <svg v-else-if="transportIcon === 'ws'" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12c2-2 5-2 7 0s5 2 7 0"/><path d="M5 17c2-2 5-2 7 0s5 2 7 0"/><path d="M5 7c2-2 5-2 7 0s5 2 7 0"/></svg>
          <svg v-else-if="transportIcon === 'stdio'" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
          <svg v-else-if="transportIcon === 'sse'" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>
          <svg v-else width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
          <code>{{ backend.transport }}</code>
        </span>
        <span class="chip" :class="{ 'chip-off': !backend.enabled }">
          <span class="dot-tiny"></span>
          {{ backend.enabled ? 'enabled' : 'disabled' }}
        </span>
      </div>

      <div class="metrics">
        <div class="metric">
          <span class="m-label">requests</span>
          <span class="m-value">{{ backend.requests.toLocaleString() }}</span>
        </div>
        <div class="metric">
          <span class="m-label">errors</span>
          <span class="m-value" :class="{ 'is-err': backend.errors > 0 }">
            {{ backend.errors.toLocaleString() }}
            <span v-if="backend.requests > 0" class="m-sub">{{ errorRate.toFixed(1) }}%</span>
          </span>
        </div>
      </div>

      <div class="latency">
        <div class="lat-head">
          <span>latency</span>
          <span class="lat-unit">ms</span>
        </div>
        <div class="lat-grid">
          <div class="lat-cell">
            <span class="lat-tag">p50</span>
            <span class="lat-val">{{ fmtMs(backend.latency_p50) }}</span>
          </div>
          <div class="lat-cell">
            <span class="lat-tag">p95</span>
            <span class="lat-val">{{ fmtMs(backend.latency_p95) }}</span>
          </div>
          <div class="lat-cell">
            <span class="lat-tag">p99</span>
            <span class="lat-val">{{ fmtMs(backend.latency_p99) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card {
  position: relative;
  border-radius: var(--radius-lg);
  padding: 1px; /* room for gradient border */
  background: var(--border-1);
  transition: transform 220ms cubic-bezier(0.2, 0.7, 0.2, 1), box-shadow 220ms ease;
}
.card::before {
  content: ''; position: absolute; inset: 0;
  border-radius: inherit;
  padding: 1px; pointer-events: none;
  background: var(--health-grad, linear-gradient(135deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02)));
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor; mask-composite: exclude;
  opacity: 0.85;
  transition: opacity 220ms ease;
}
.card:hover { transform: translateY(-2px); }
.card:hover::before { opacity: 1; }
.card:hover { box-shadow: 0 12px 30px -10px rgba(0,0,0,0.5); }

.card.health-healthy   { --health-grad: linear-gradient(135deg, rgba(52,211,153,0.6), rgba(0,212,255,0.25) 60%, rgba(255,255,255,0.04)); }
.card.health-unknown   { --health-grad: linear-gradient(135deg, rgba(251,191,36,0.55), rgba(255,255,255,0.04) 60%); }
.card.health-unhealthy { --health-grad: linear-gradient(135deg, rgba(251,113,133,0.7), rgba(124,92,255,0.2) 60%, rgba(255,255,255,0.04)); }

.card.disabled { opacity: 0.62; filter: saturate(0.6); }

.card-inner {
  position: relative;
  background: linear-gradient(180deg, rgba(22,26,37,0.92), rgba(17,20,29,0.92));
  border-radius: calc(var(--radius-lg) - 1px);
  padding: 1rem 1.1rem 1.1rem;
  display: flex; flex-direction: column; gap: 0.85rem;
  height: 100%;
}

/* Header */
.card-head { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; }
.title-row { display: flex; align-items: center; gap: 0.55rem; min-width: 0; }
.name {
  font-size: 0.95rem; font-weight: 600; letter-spacing: -0.01em;
  color: var(--text-1);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.status-dot {
  position: relative;
  width: 10px; height: 10px; border-radius: 50%;
  flex: none;
  background: var(--text-4);
}
.status-dot .ring {
  position: absolute; inset: -4px; border-radius: 50%;
  border: 1px solid currentColor; opacity: 0;
}
.status-dot.s-healthy { background: var(--ok); color: var(--ok); box-shadow: 0 0 12px rgba(52, 211, 153, 0.55); }
.status-dot.s-healthy .ring { animation: pulse-ring 1.8s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
.status-dot.s-unknown { background: var(--warn); color: var(--warn); box-shadow: 0 0 10px rgba(251, 191, 36, 0.45); }
.status-dot.s-unknown .ring { animation: pulse-ring 2.2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
.status-dot.s-unhealthy { background: var(--err); color: var(--err); box-shadow: 0 0 12px rgba(251, 113, 133, 0.6); }
.status-dot.s-unhealthy .ring { animation: pulse-ring 1.2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }

@keyframes pulse-ring {
  0% { transform: scale(0.7); opacity: 0.9; }
  80%, 100% { transform: scale(2.4); opacity: 0; }
}

.health-tag {
  font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.12em;
  padding: 3px 8px; border-radius: 999px;
  font-weight: 600;
  border: 1px solid transparent;
}
.tag-healthy   { background: var(--ok-soft); color: var(--ok); border-color: rgba(52,211,153,0.3); }
.tag-unknown   { background: var(--warn-soft); color: var(--warn); border-color: rgba(251,191,36,0.3); }
.tag-unhealthy { background: var(--err-soft); color: var(--err); border-color: rgba(251,113,133,0.35); }

/* Meta chips */
.meta { display: flex; flex-wrap: wrap; gap: 0.35rem; }
.chip {
  display: inline-flex; align-items: center; gap: 0.35rem;
  padding: 3px 8px; border-radius: 6px;
  background: var(--surface-glass);
  border: 1px solid var(--border-1);
  color: var(--text-3);
  font-size: 0.72rem;
}
.chip code { font-size: 0.7rem; color: var(--text-mono); }
.chip svg { color: var(--text-3); }
.dot-tiny {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--ok); box-shadow: 0 0 6px rgba(52,211,153,0.6);
}
.chip-off .dot-tiny { background: var(--text-4); box-shadow: none; }
.chip-off { color: var(--text-4); }

/* Metrics row */
.metrics {
  display: grid; grid-template-columns: 1fr 1fr; gap: 0.65rem;
  padding-top: 0.25rem;
}
.metric {
  display: flex; flex-direction: column; gap: 0.15rem;
  padding: 0.55rem 0.7rem;
  background: var(--surface-glass);
  border: 1px solid var(--border-1);
  border-radius: var(--radius-md);
}
.m-label { font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-4); font-weight: 600; }
.m-value {
  font-size: 1.05rem; font-weight: 600; color: var(--text-1);
  font-variant-numeric: tabular-nums;
  display: flex; align-items: baseline; gap: 0.35rem;
}
.m-value.is-err { color: var(--err); }
.m-sub { font-size: 0.7rem; font-weight: 500; color: var(--text-4); }
.m-value.is-err .m-sub { color: var(--err); opacity: 0.8; }

/* Latency block */
.latency {
  display: flex; flex-direction: column; gap: 0.4rem;
  padding: 0.6rem 0.7rem;
  background: linear-gradient(180deg, rgba(124,92,255,0.06), rgba(0,212,255,0.04));
  border: 1px solid var(--border-1);
  border-radius: var(--radius-md);
}
.lat-head {
  display: flex; align-items: center; justify-content: space-between;
  font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.1em;
  color: var(--text-4); font-weight: 600;
}
.lat-unit { font-family: var(--font-mono); text-transform: lowercase; letter-spacing: 0.04em; }
.lat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; }
.lat-cell { display: flex; flex-direction: column; align-items: flex-start; gap: 2px; }
.lat-tag {
  font-family: var(--font-mono); font-size: 0.65rem;
  color: var(--accent-2); letter-spacing: 0.04em;
}
.lat-val {
  font-family: var(--font-mono); font-size: 0.95rem; font-weight: 500;
  color: var(--text-1); font-variant-numeric: tabular-nums;
}
</style>
