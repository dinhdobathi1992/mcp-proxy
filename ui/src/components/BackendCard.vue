<script setup lang="ts">
import type { BackendStatus } from '../types'

defineProps<{ backend: BackendStatus }>()

function healthColor(health: string) {
  if (health === 'healthy') return '#4ade80'
  if (health === 'unhealthy') return '#f87171'
  return '#fbbf24'
}
</script>

<template>
  <div class="backend-card">
    <div class="header">
      <span class="name">{{ backend.name }}</span>
      <span class="badge" :style="{ background: healthColor(backend.health) }">
        {{ backend.health }}
      </span>
    </div>
    <div class="stats">
      <div><span class="label">Transport:</span> {{ backend.transport }}</div>
      <div><span class="label">Requests:</span> {{ backend.requests }}</div>
      <div><span class="label">Errors:</span> {{ backend.errors }}</div>
      <div><span class="label">Latency p50:</span> {{ backend.latency_p50.toFixed(1) }}ms</div>
      <div><span class="label">Latency p95:</span> {{ backend.latency_p95.toFixed(1) }}ms</div>
      <div><span class="label">Latency p99:</span> {{ backend.latency_p99.toFixed(1) }}ms</div>
    </div>
  </div>
</template>

<style scoped>
.backend-card { background: white; border-radius: 8px; padding: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }
.name { font-weight: 600; font-size: 1.1rem; }
.badge { padding: 0.25rem 0.5rem; border-radius: 4px; color: white; font-size: 0.75rem; text-transform: uppercase; }
.stats { display: grid; gap: 0.25rem; font-size: 0.9rem; }
.label { color: #666; }
</style>
