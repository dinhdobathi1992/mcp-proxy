<script setup lang="ts">
import { ref } from 'vue'
import StatusDashboard from './components/StatusDashboard.vue'
import AdminPanel from './components/AdminPanel.vue'

const uiMode = ref<'default' | 'advanced'>('advanced')
</script>

<template>
  <div id="app">
    <header>
      <h1>mcp-proxy Dashboard</h1>
      <div class="mode-toggle">
        <button :class="{ active: uiMode === 'default' }" @click="uiMode = 'default'">Status</button>
        <button :class="{ active: uiMode === 'advanced' }" @click="uiMode = 'advanced'">Admin</button>
      </div>
    </header>
    <main>
      <StatusDashboard />
      <AdminPanel v-if="uiMode === 'advanced'" :data="null" />
    </main>
  </div>
</template>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; }
header { background: #1a1a2e; color: white; padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; }
main { padding: 2rem; }
.mode-toggle { display: flex; gap: 0.5rem; }
.mode-toggle button { padding: 0.5rem 1rem; border: 1px solid rgba(255,255,255,0.3); border-radius: 4px; background: transparent; color: white; cursor: pointer; }
.mode-toggle button.active { background: rgba(255,255,255,0.2); border-color: white; }
</style>
