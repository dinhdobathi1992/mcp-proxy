<script setup lang="ts">
import { ref } from 'vue'
import type { StatusSnapshot } from '../types'

defineProps<{ data: StatusSnapshot | null }>()

const message = ref('')

async function sendCommand(action: string, args: Record<string, unknown> = {}) {
  const id = `cmd-${Date.now()}`
  const cmd = { id, action, args, timestamp: new Date().toISOString() }

  try {
    const resp = await fetch('/api/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cmd),
    })
    const result = await resp.json()
    message.value = result.message || 'Command sent'
  } catch (e) {
    message.value = `Error: ${e}`
  }

  setTimeout(() => { message.value = '' }, 3000)
}
</script>

<template>
  <div class="admin-panel">
    <h2>Admin Panel</h2>

    <div v-if="message" class="message">{{ message }}</div>

    <div class="actions">
      <button @click="sendCommand('reload_config')">Reload Config</button>

      <div v-for="backend in data?.backends" :key="backend.name" class="backend-actions">
        <span>{{ backend.name }}</span>
        <button
          v-if="backend.enabled"
          @click="sendCommand('disable_backend', { name: backend.name })"
        >
          Disable
        </button>
        <button
          v-else
          @click="sendCommand('enable_backend', { name: backend.name })"
        >
          Enable
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-panel { background: white; border-radius: 8px; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-top: 2rem; }
.admin-panel h2 { margin-bottom: 1rem; }
.message { padding: 0.5rem; background: #e0f2fe; border-radius: 4px; margin-bottom: 1rem; }
.actions { display: flex; flex-direction: column; gap: 0.5rem; }
.backend-actions { display: flex; align-items: center; gap: 1rem; padding: 0.5rem; background: #f9fafb; border-radius: 4px; }
button { padding: 0.5rem 1rem; border: none; border-radius: 4px; background: #3b82f6; color: white; cursor: pointer; }
button:hover { background: #2563eb; }
</style>
