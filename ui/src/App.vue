<script setup lang="ts">
import { computed, ref } from 'vue'
import StatusDashboard from './components/StatusDashboard.vue'
import AdminPanel from './components/AdminPanel.vue'
import { useWebSocket } from './composables/useWebSocket'

const uiMode = ref<'status' | 'admin'>('status')

const wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`
const { data, connected } = useWebSocket(wsUrl)

const proxyName = computed(() => data.value?.proxy_name ?? 'mcp-proxy')
const lastUpdate = computed(() => {
  if (!data.value) return null
  return new Date(data.value.timestamp).toLocaleTimeString()
})
</script>

<template>
  <div class="app-shell" :class="`mode-${uiMode}`">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">
          <svg width="22" height="22" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M16 2L28 8.5V23.5L16 30L4 23.5V8.5L16 2Z" fill="url(#hex-grad)"/>
            <path d="M16 2L28 8.5V23.5L16 30L4 23.5V8.5L16 2Z" stroke="rgba(255,255,255,0.3)" stroke-width="0.5" fill="none"/>
            <path d="M10 16L14 18.5V22.5L18 20L22 22.5V18.5L18 16L14 18.5V14.5L10 16Z" fill="rgba(255,255,255,0.9)"/>
            <path d="M22 10.5L18 13V16L22 18.5" stroke="rgba(255,255,255,0.6)" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            <path d="M10 21.5L14 19V16L10 13.5" stroke="rgba(255,255,255,0.6)" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            <defs>
              <linearGradient id="hex-grad" x1="4" y1="2" x2="28" y2="30" gradientUnits="userSpaceOnUse">
                <stop stop-color="#7c5cff"/>
                <stop offset="1" stop-color="#00d4ff"/>
              </linearGradient>
            </defs>
          </svg>
        </div>
        <div class="brand-text">
          <div class="brand-name">{{ proxyName }}</div>
        </div>
      </div>

      <nav class="nav">
        <button
          class="nav-item"
          :class="{ active: uiMode === 'status' }"
          @click="uiMode = 'status'"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 12h4l3-9 4 18 3-9h4"/>
          </svg>
          <span>Status</span>
        </button>
        <button
          class="nav-item"
          :class="{ active: uiMode === 'admin' }"
          @click="uiMode = 'admin'"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
          <span>Admin</span>
          <span v-if="uiMode === 'admin'" class="badge-power">POWER</span>
        </button>
      </nav>

      <div class="sidebar-footer">
        <div class="conn" :class="{ live: connected }">
          <span class="dot"><span class="pulse"></span></span>
          <span class="conn-text">{{ connected ? 'Live' : 'Reconnecting…' }}</span>
        </div>
        <div v-if="lastUpdate" class="last-update">
          <span>updated</span>
          <code>{{ lastUpdate }}</code>
        </div>
      </div>
    </aside>

    <main class="main">
      <header class="topbar">
        <div class="topbar-left">
          <div class="page-title">
            <span class="kicker">{{ uiMode === 'status' ? 'Overview' : 'Operations' }}</span>
            <h1>{{ uiMode === 'status' ? 'Backend health & traffic' : 'Admin controls' }}</h1>
          </div>
        </div>
        <div class="topbar-right">
          <div class="conn-pill" :class="{ live: connected }">
            <span class="dot"><span class="pulse"></span></span>
            {{ connected ? 'connected' : 'offline' }}
          </div>
        </div>
      </header>

      <section class="content">
        <StatusDashboard v-if="uiMode === 'status'" :data="data" :connected="connected" />
        <AdminPanel v-else :data="data" :connected="connected" />
      </section>
    </main>
  </div>
</template>

<style>
:root {
  /* Surface palette */
  --bg-0: #07080c;
  --bg-1: #0b0d14;
  --bg-2: #11141d;
  --bg-3: #161a25;
  --bg-elev: #1a1f2c;
  --surface-card: rgba(22, 26, 37, 0.75);
  --surface-card-strong: rgba(28, 33, 46, 0.92);
  --surface-glass: rgba(255, 255, 255, 0.03);

  /* Borders */
  --border-1: rgba(255, 255, 255, 0.06);
  --border-2: rgba(255, 255, 255, 0.10);
  --border-3: rgba(255, 255, 255, 0.16);

  /* Text */
  --text-1: #f5f6fa;
  --text-2: #c5cad6;
  --text-3: #8a90a2;
  --text-4: #5b6173;
  --text-mono: #b8bdcc;

  /* Brand & accents */
  --accent: #7c5cff;
  --accent-2: #00d4ff;
  --accent-glow: rgba(124, 92, 255, 0.45);
  --accent-soft: rgba(124, 92, 255, 0.12);

  /* Semantic */
  --ok: #34d399;
  --ok-soft: rgba(52, 211, 153, 0.15);
  --warn: #fbbf24;
  --warn-soft: rgba(251, 191, 36, 0.15);
  --err: #fb7185;
  --err-soft: rgba(251, 113, 133, 0.15);
  --info: #60a5fa;
  --info-soft: rgba(96, 165, 250, 0.15);

  /* Gradients */
  --grad-ok: linear-gradient(135deg, #34d399 0%, #10b981 100%);
  --grad-warn: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
  --grad-err: linear-gradient(135deg, #fb7185 0%, #e11d48 100%);
  --grad-accent: linear-gradient(135deg, #7c5cff 0%, #00d4ff 100%);
  --grad-admin: linear-gradient(135deg, #ff6b6b 0%, #f59e0b 50%, #7c5cff 100%);

  /* Effects */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 14px rgba(0, 0, 0, 0.35);
  --shadow-lg: 0 18px 50px rgba(0, 0, 0, 0.5);
  --ring-accent: 0 0 0 1px var(--accent), 0 0 24px var(--accent-glow);

  /* Type */
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;

  /* Layout */
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --radius-xl: 20px;
  --sidebar-w: 240px;
}

@supports (font-variation-settings: normal) {
  :root { --font-sans: 'Inter var', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
}

* { margin: 0; padding: 0; box-sizing: border-box; }

html, body, #app {
  height: 100%;
  background: var(--bg-0);
  color: var(--text-1);
  font-family: var(--font-sans);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  font-feature-settings: 'cv02', 'cv03', 'cv04', 'cv11';
}

body {
  background:
    radial-gradient(1200px 600px at 80% -10%, rgba(124, 92, 255, 0.08), transparent 60%),
    radial-gradient(900px 500px at -10% 100%, rgba(0, 212, 255, 0.06), transparent 60%),
    var(--bg-0);
  background-attachment: fixed;
}

button { font: inherit; color: inherit; cursor: pointer; }
code { font-family: var(--font-mono); }

::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-2); border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: var(--border-3); }

.app-shell {
  display: grid;
  grid-template-columns: var(--sidebar-w) 1fr;
  min-height: 100vh;
}

/* Sidebar -------------------------------------------------- */
.sidebar {
  position: sticky; top: 0; align-self: start;
  height: 100vh;
  display: flex; flex-direction: column;
  padding: 1.25rem 0.875rem;
  border-right: 1px solid var(--border-1);
  background: linear-gradient(180deg, var(--bg-1) 0%, var(--bg-0) 100%);
  z-index: 10;
}

.brand { display: flex; align-items: center; gap: 0.65rem; padding: 0.25rem 0.5rem 1.5rem; }
.brand-mark {
  width: 34px; height: 34px;
  display: grid; place-items: center;
  border-radius: 9px;
  background: var(--grad-accent);
  color: #fff;
  box-shadow: 0 4px 16px rgba(124, 92, 255, 0.4), inset 0 1px 0 rgba(255,255,255,0.25);
}
.brand-text { line-height: 1.15; }
.brand-name { font-weight: 700; font-size: 1rem; letter-spacing: -0.02em; background: var(--grad-accent); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.brand-sub { display: none; }

.nav { display: flex; flex-direction: column; gap: 2px; }
.nav-item {
  display: flex; align-items: center; gap: 0.65rem;
  width: 100%; padding: 0.55rem 0.65rem;
  background: transparent; border: 1px solid transparent;
  border-radius: var(--radius-md);
  color: var(--text-3);
  font-size: 0.85rem; font-weight: 500;
  text-align: left;
  transition: background 120ms ease, color 120ms ease, border-color 120ms ease;
}
.nav-item:hover { background: var(--surface-glass); color: var(--text-2); }
.nav-item.active {
  color: var(--text-1);
  background: var(--accent-soft);
  border-color: rgba(124, 92, 255, 0.25);
}
.nav-item.active svg { color: var(--accent); }
.nav-item span { flex: 1; }

.badge-power {
  font-size: 0.6rem; letter-spacing: 0.12em;
  padding: 2px 6px; border-radius: 4px;
  background: var(--grad-admin);
  color: #fff;
  font-weight: 700;
}

.sidebar-footer { margin-top: auto; display: flex; flex-direction: column; gap: 0.5rem; padding: 0.5rem 0.65rem 0.25rem; }

.conn {
  display: inline-flex; align-items: center; gap: 0.5rem;
  font-size: 0.8rem; color: var(--text-3);
}
.conn .dot {
  position: relative;
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--err); flex: none;
  box-shadow: 0 0 0 0 rgba(0,0,0,0);
}
.conn .pulse {
  position: absolute; inset: -3px; border-radius: 50%;
  border: 1px solid var(--err); opacity: 0; animation: none;
}
.conn.live .dot { background: var(--ok); }
.conn.live .pulse { border-color: var(--ok); animation: pulse-ring 1.6s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
.conn.live .conn-text { color: var(--text-2); }

.last-update { display: flex; align-items: center; gap: 0.4rem; font-size: 0.72rem; color: var(--text-4); }
.last-update code { color: var(--text-mono); font-size: 0.72rem; }

@keyframes pulse-ring {
  0% { transform: scale(0.8); opacity: 0.9; }
  80%, 100% { transform: scale(2.2); opacity: 0; }
}

/* Main ----------------------------------------------------- */
.main { display: flex; flex-direction: column; min-width: 0; }

.topbar {
  position: sticky; top: 0; z-index: 5;
  display: flex; align-items: center; justify-content: space-between;
  padding: 1.25rem 2rem;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  background: linear-gradient(180deg, rgba(11,13,20,0.85), rgba(11,13,20,0.55));
  border-bottom: 1px solid var(--border-1);
}

.page-title .kicker {
  font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.12em;
  color: var(--text-4); display: block; margin-bottom: 0.15rem;
}
.page-title h1 {
  font-size: 1.35rem; font-weight: 600; letter-spacing: -0.02em; color: var(--text-1);
}

.conn-pill {
  display: inline-flex; align-items: center; gap: 0.5rem;
  padding: 0.4rem 0.7rem;
  border: 1px solid var(--border-2);
  border-radius: 999px;
  background: var(--surface-glass);
  font-size: 0.75rem; color: var(--text-3);
  font-variant: tabular-nums;
}
.conn-pill .dot {
  position: relative; width: 7px; height: 7px; border-radius: 50%;
  background: var(--err); flex: none;
}
.conn-pill .pulse { position: absolute; inset: -3px; border-radius: 50%; border: 1px solid var(--err); opacity: 0; }
.conn-pill.live .dot { background: var(--ok); }
.conn-pill.live { color: var(--ok); border-color: rgba(52,211,153,0.25); background: var(--ok-soft); }
.conn-pill.live .pulse { border-color: var(--ok); animation: pulse-ring 1.6s cubic-bezier(0.4, 0, 0.6, 1) infinite; }

.content { padding: 2rem; flex: 1; min-width: 0; }

/* Admin mode tints the shell */
.app-shell.mode-admin .topbar {
  background:
    linear-gradient(180deg, rgba(20,12,16,0.85), rgba(20,12,16,0.55));
  border-bottom-color: rgba(255, 107, 107, 0.18);
}
.app-shell.mode-admin .topbar::after {
  content: ''; position: absolute; left: 0; right: 0; bottom: -1px; height: 1px;
  background: var(--grad-admin); opacity: 0.6;
}
.topbar { position: sticky; }

/* Responsive ---------------------------------------------- */
@media (max-width: 900px) {
  :root { --sidebar-w: 100%; }
  .app-shell { grid-template-columns: 1fr; }
  .sidebar {
    position: static; height: auto;
    flex-direction: row; align-items: center; gap: 0.75rem;
    padding: 0.75rem 1rem;
    border-right: none; border-bottom: 1px solid var(--border-1);
  }
  .brand { padding: 0; flex: none; }
  .nav { flex-direction: row; flex: 1; gap: 4px; justify-content: center; }
  .nav-item span { display: none; }
  .nav-item { padding: 0.5rem 0.7rem; }
  .nav-item.active span, .badge-power { display: inline; }
  .sidebar-footer { margin-top: 0; flex-direction: row; align-items: center; gap: 0.75rem; padding: 0; }
  .last-update { display: none; }
  .topbar { padding: 1rem; }
  .content { padding: 1rem; }
  .page-title h1 { font-size: 1.1rem; }
}
</style>
