<script setup lang="ts">
import StatusDashboard from './components/StatusDashboard.vue'
</script>

<template>
  <div id="app">
    <header>
      <h1>mcp-proxy Dashboard</h1>
    </header>
    <main>
      <StatusDashboard />
    </main>
  </div>
</template>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; }
header { background: #1a1a2e; color: white; padding: 1rem 2rem; }
main { padding: 2rem; }
</style>
