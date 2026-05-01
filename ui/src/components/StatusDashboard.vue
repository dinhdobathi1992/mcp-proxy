<script setup lang="ts">
import { useWebSocket } from '../composables/useWebSocket'
import BackendCard from './BackendCard.vue'

const { data, connected } = useWebSocket(`ws://${location.host}/ws`)
</script>

<template>
  <div class="dashboard">
    <div class="connection" :class="{ online: connected }">
      {{ connected ? 'Connected' : 'Disconnected' }}
    </div>

    <div v-if="data" class="summary">
      <div class="stat">
        <div class="value">{{ data.totals.backends }}</div>
        <div class="label">Backends</div>
      </div>
      <div class="stat">
        <div class="value">{{ data.totals.healthy }}</div>
        <div class="label">Healthy</div>
      </div>
      <div class="stat">
        <div class="value">{{ data.totals.requests }}</div>
        <div class="label">Requests</div>
      </div>
      <div class="stat">
        <div class="value">{{ data.totals.errors }}</div>
        <div class="label">Errors</div>
      </div>
    </div>

    <div v-if="data" class="backends">
      <BackendCard
        v-for="backend in data.backends"
        :key="backend.name"
        :backend="backend"
      />
    </div>

    <div v-if="data" class="timestamp">
      Last update: {{ new Date(data.timestamp).toLocaleTimeString() }}
    </div>
  </div>
</template>

<style scoped>
.dashboard { max-width: 1200px; margin: 0 auto; }
.connection { display: inline-block; padding: 0.25rem 0.75rem; border-radius: 4px; background: #f87171; color: white; margin-bottom: 1rem; }
.connection.online { background: #4ade80; }
.summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 2rem; }
.stat { background: white; padding: 1rem; border-radius: 8px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.stat .value { font-size: 2rem; font-weight: 700; }
.stat .label { color: #666; font-size: 0.875rem; }
.backends { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1rem; margin-bottom: 1rem; }
.timestamp { color: #999; font-size: 0.75rem; text-align: right; }
</style>
