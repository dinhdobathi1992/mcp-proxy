<script setup lang="ts">
import { computed, ref } from 'vue'
import type { StatusSnapshot } from '../types'

const props = defineProps<{ data: StatusSnapshot | null; connected: boolean }>()

interface ToastMsg {
  id: number
  text: string
  kind: 'ok' | 'err' | 'info'
}

const toasts = ref<ToastMsg[]>([])
const pending = ref<Set<string>>(new Set())
let toastSeq = 0

function pushToast(text: string, kind: ToastMsg['kind']) {
  const id = ++toastSeq
  toasts.value.push({ id, text, kind })
  setTimeout(() => {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }, 3500)
}

async function sendCommand(action: string, args: Record<string, unknown> = {}) {
  const key = `${action}:${JSON.stringify(args)}`
  if (pending.value.has(key)) return
  pending.value.add(key)

  const id = `cmd-${Date.now()}`
  const cmd = { id, action, args, timestamp: new Date().toISOString() }

  try {
    const resp = await fetch('/api/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cmd),
    })
    const result = await resp.json().catch(() => ({}))
    const ok = resp.ok && result.status !== 'error'
    pushToast(result.message || (ok ? 'Command accepted' : 'Command failed'), ok ? 'ok' : 'err')
  } catch (e) {
    pushToast(`Network error: ${e}`, 'err')
  } finally {
    pending.value.delete(key)
  }
}

const enabledCount = computed(() => props.data?.backends.filter(b => b.enabled).length ?? 0)
const disabledCount = computed(() => props.data?.backends.filter(b => !b.enabled).length ?? 0)

function isPending(action: string, name?: string) {
  const key = `${action}:${JSON.stringify(name ? { name } : {})}`
  return pending.value.has(key)
}
</script>

<template>
  <div class="admin">
    <!-- Toasts -->
    <div class="toast-stack" role="status" aria-live="polite">
      <transition-group name="toast">
        <div
          v-for="t in toasts"
          :key="t.id"
          class="toast"
          :class="`toast-${t.kind}`"
        >
          <span class="toast-icon" v-if="t.kind === 'ok'">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
          </span>
          <span class="toast-icon" v-else-if="t.kind === 'err'">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          </span>
          <span class="toast-icon" v-else>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          </span>
          {{ t.text }}
        </div>
      </transition-group>
    </div>

    <!-- Banner -->
    <div class="banner">
      <div class="banner-glow"></div>
      <div class="banner-content">
        <span class="banner-tag">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2L2 7v10l10 5 10-5V7L12 2z"/><path d="M2 7l10 5 10-5"/><line x1="12" y1="22" x2="12" y2="12"/>
          </svg>
          Privileged controls
        </span>
        <h2>Operate the proxy without restarting it</h2>
        <p>Commands are dispatched over the control channel. Effects propagate live to the status feed.</p>
      </div>
    </div>

    <!-- Global ops -->
    <section class="block">
      <div class="block-head">
        <h3>Global</h3>
        <div class="block-meta">
          <span class="kbd">⌘</span><span class="meta-text">authenticated control plane</span>
        </div>
      </div>
      <div class="grid-actions">
        <button
          class="action action-primary"
          :disabled="isPending('reload_config')"
          @click="sendCommand('reload_config')"
        >
          <span class="action-ic">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
          </span>
          <span class="action-body">
            <span class="action-title">Reload config</span>
            <span class="action-sub">Re-read disk, swap live without restart</span>
          </span>
          <span class="action-arrow">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
          </span>
        </button>
      </div>
    </section>

    <!-- Backends control -->
    <section class="block">
      <div class="block-head">
        <h3>Backends</h3>
        <div class="counters">
          <span class="counter counter-ok">{{ enabledCount }} enabled</span>
          <span class="counter counter-off">{{ disabledCount }} disabled</span>
        </div>
      </div>

      <div v-if="!data || data.backends.length === 0" class="empty-row">
        <span>No backends to manage.</span>
      </div>

      <div v-else class="rows">
        <div
          v-for="b in data.backends"
          :key="b.name"
          class="row"
          :class="{ 'row-off': !b.enabled }"
        >
          <div class="row-id">
            <span class="row-dot" :class="`s-${b.health}`"></span>
            <div class="row-text">
              <div class="row-name">{{ b.name }}</div>
              <div class="row-sub">
                <code>{{ b.transport }}</code>
                <span class="sep">·</span>
                <span>{{ b.requests.toLocaleString() }} req</span>
                <span class="sep" v-if="b.errors > 0">·</span>
                <span v-if="b.errors > 0" class="row-err">{{ b.errors }} err</span>
              </div>
            </div>
          </div>

          <div class="row-actions">
            <span class="state-pill" :class="b.enabled ? 'state-on' : 'state-off'">
              {{ b.enabled ? 'enabled' : 'disabled' }}
            </span>
            <button
              v-if="b.enabled"
              class="btn btn-ghost-danger"
              :disabled="isPending('disable_backend', b.name)"
              @click="sendCommand('disable_backend', { name: b.name })"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>
              Disable
            </button>
            <button
              v-else
              class="btn btn-ghost-ok"
              :disabled="isPending('enable_backend', b.name)"
              @click="sendCommand('enable_backend', { name: b.name })"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              Enable
            </button>
          </div>
        </div>
      </div>
    </section>

    <div v-if="!connected" class="offline-warn">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
      Live channel offline — commands will still POST but state will not update until reconnected.
    </div>
  </div>
</template>

<style scoped>
.admin {
  position: relative;
  max-width: 1080px; margin: 0 auto;
  display: flex; flex-direction: column; gap: 1.25rem;
}

/* Banner --------------------------------------------- */
.banner {
  position: relative;
  border-radius: var(--radius-xl);
  padding: 1.5rem 1.75rem;
  overflow: hidden;
  border: 1px solid rgba(255, 107, 107, 0.18);
  background:
    linear-gradient(135deg, rgba(255, 107, 107, 0.10), rgba(124, 92, 255, 0.06)),
    var(--bg-2);
}
.banner-glow {
  position: absolute; inset: -40% -10% auto auto;
  width: 60%; height: 200%;
  background: radial-gradient(closest-side, rgba(255, 107, 107, 0.35), transparent 70%);
  filter: blur(40px);
  pointer-events: none;
}
.banner-content { position: relative; }
.banner-tag {
  display: inline-flex; align-items: center; gap: 0.4rem;
  font-size: 0.7rem; font-weight: 600;
  padding: 4px 9px; border-radius: 999px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  color: var(--text-2);
  text-transform: uppercase; letter-spacing: 0.1em;
  margin-bottom: 0.7rem;
}
.banner-tag svg { color: #ffb088; }
.banner h2 {
  font-size: 1.3rem; font-weight: 600; letter-spacing: -0.02em;
  background: var(--grad-admin);
  -webkit-background-clip: text; background-clip: text;
  color: transparent;
}
.banner p { color: var(--text-3); font-size: 0.85rem; margin-top: 0.3rem; max-width: 56ch; }

/* Block --------------------------------------------- */
.block {
  background: var(--surface-card);
  border: 1px solid var(--border-1);
  border-radius: var(--radius-lg);
  padding: 1.1rem 1.2rem 1.2rem;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}
.block-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 0.9rem;
}
.block-head h3 { font-size: 0.85rem; font-weight: 600; color: var(--text-2); letter-spacing: -0.01em; }
.block-meta { display: flex; align-items: center; gap: 0.45rem; font-size: 0.72rem; color: var(--text-4); }
.kbd {
  font-family: var(--font-mono);
  padding: 1px 6px; border-radius: 4px;
  border: 1px solid var(--border-2); background: var(--surface-glass);
  font-size: 0.7rem; color: var(--text-3);
}
.meta-text { letter-spacing: 0.02em; }

.counters { display: flex; align-items: center; gap: 0.35rem; }
.counter { font-size: 0.7rem; padding: 3px 8px; border-radius: 999px; border: 1px solid var(--border-1); }
.counter-ok  { background: var(--ok-soft); color: var(--ok); border-color: rgba(52,211,153,0.3); }
.counter-off { background: var(--surface-glass); color: var(--text-3); }

/* Action grid --------------------------------------- */
.grid-actions { display: grid; gap: 0.6rem; }

.action {
  display: grid;
  grid-template-columns: 36px 1fr auto;
  gap: 0.85rem; align-items: center;
  padding: 0.8rem 0.95rem;
  background: var(--surface-glass);
  border: 1px solid var(--border-1);
  border-radius: var(--radius-md);
  text-align: left; color: var(--text-2);
  transition: background 160ms ease, border-color 160ms ease, transform 160ms ease;
}
.action:hover:not(:disabled) {
  background: rgba(124, 92, 255, 0.08);
  border-color: rgba(124, 92, 255, 0.28);
  transform: translateY(-1px);
  color: var(--text-1);
}
.action:active:not(:disabled) { transform: translateY(0); }
.action:disabled { opacity: 0.5; cursor: progress; }

.action-ic {
  width: 36px; height: 36px; display: grid; place-items: center;
  border-radius: 9px;
  background: var(--accent-soft);
  border: 1px solid rgba(124, 92, 255, 0.25);
  color: var(--accent);
}
.action-body { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.action-title { font-weight: 600; font-size: 0.9rem; color: var(--text-1); }
.action-sub { font-size: 0.75rem; color: var(--text-3); }
.action-arrow { color: var(--text-4); transition: transform 160ms ease, color 160ms ease; }
.action:hover:not(:disabled) .action-arrow { color: var(--accent); transform: translateX(2px); }

/* Rows ---------------------------------------------- */
.rows { display: flex; flex-direction: column; gap: 0.45rem; }

.row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 1rem; align-items: center;
  padding: 0.7rem 0.9rem;
  background: var(--surface-glass);
  border: 1px solid var(--border-1);
  border-radius: var(--radius-md);
  transition: background 140ms ease, border-color 140ms ease;
}
.row:hover { background: rgba(255,255,255,0.04); border-color: var(--border-2); }
.row.row-off { opacity: 0.7; }

.row-id { display: flex; align-items: center; gap: 0.7rem; min-width: 0; }
.row-dot { width: 8px; height: 8px; border-radius: 50%; flex: none; background: var(--text-4); }
.row-dot.s-healthy { background: var(--ok); box-shadow: 0 0 8px rgba(52,211,153,0.5); }
.row-dot.s-unknown { background: var(--warn); box-shadow: 0 0 8px rgba(251,191,36,0.5); }
.row-dot.s-unhealthy { background: var(--err); box-shadow: 0 0 8px rgba(251,113,133,0.5); }

.row-text { min-width: 0; }
.row-name {
  font-size: 0.9rem; font-weight: 500; color: var(--text-1);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.row-sub {
  display: flex; align-items: center; gap: 0.35rem;
  font-size: 0.72rem; color: var(--text-3);
  margin-top: 1px; flex-wrap: wrap;
}
.row-sub code { font-size: 0.7rem; color: var(--text-mono); }
.row-sub .sep { color: var(--text-4); }
.row-err { color: var(--err); }

.row-actions { display: flex; align-items: center; gap: 0.5rem; }

.state-pill {
  font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.1em;
  padding: 3px 8px; border-radius: 999px; font-weight: 600;
  border: 1px solid transparent;
}
.state-on { background: var(--ok-soft); color: var(--ok); border-color: rgba(52,211,153,0.25); }
.state-off { background: var(--surface-glass); color: var(--text-3); border-color: var(--border-1); }

.btn {
  display: inline-flex; align-items: center; gap: 0.35rem;
  padding: 0.45rem 0.75rem;
  border: 1px solid var(--border-2);
  border-radius: 8px;
  background: transparent; color: var(--text-2);
  font-size: 0.78rem; font-weight: 500;
  transition: background 140ms ease, border-color 140ms ease, color 140ms ease, transform 140ms ease;
}
.btn:hover:not(:disabled) { transform: translateY(-1px); }
.btn:disabled { opacity: 0.5; cursor: progress; }

.btn-ghost-ok:hover:not(:disabled) {
  background: var(--ok-soft); color: var(--ok); border-color: rgba(52,211,153,0.4);
}
.btn-ghost-danger:hover:not(:disabled) {
  background: var(--err-soft); color: var(--err); border-color: rgba(251,113,133,0.4);
}

.empty-row {
  padding: 1.5rem; text-align: center;
  color: var(--text-3); font-size: 0.85rem;
  border: 1px dashed var(--border-2); border-radius: var(--radius-md);
}

/* Offline warning ----------------------------------- */
.offline-warn {
  display: flex; align-items: center; gap: 0.5rem;
  padding: 0.7rem 0.9rem;
  border-radius: var(--radius-md);
  background: var(--warn-soft);
  border: 1px solid rgba(251, 191, 36, 0.3);
  color: var(--warn);
  font-size: 0.8rem;
}

/* Toasts -------------------------------------------- */
.toast-stack {
  position: fixed; right: 1.5rem; bottom: 1.5rem; z-index: 100;
  display: flex; flex-direction: column; gap: 0.5rem; align-items: flex-end;
  pointer-events: none;
}
.toast {
  pointer-events: auto;
  display: flex; align-items: center; gap: 0.5rem;
  padding: 0.6rem 0.85rem;
  border-radius: var(--radius-md);
  background: var(--surface-card-strong);
  border: 1px solid var(--border-2);
  box-shadow: var(--shadow-lg);
  font-size: 0.82rem; color: var(--text-1);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  max-width: 360px;
}
.toast-icon { display: grid; place-items: center; flex: none; width: 18px; height: 18px; border-radius: 5px; }
.toast-ok  { border-color: rgba(52,211,153,0.35); }
.toast-ok  .toast-icon { background: var(--ok-soft); color: var(--ok); }
.toast-err { border-color: rgba(251,113,133,0.4); }
.toast-err .toast-icon { background: var(--err-soft); color: var(--err); }
.toast-info .toast-icon { background: var(--info-soft); color: var(--info); }

.toast-enter-from { opacity: 0; transform: translateY(8px) scale(0.96); }
.toast-leave-to   { opacity: 0; transform: translateY(4px) scale(0.98); }
.toast-enter-active, .toast-leave-active { transition: opacity 200ms ease, transform 200ms ease; }

/* Responsive ---------------------------------------- */
@media (max-width: 600px) {
  .row { grid-template-columns: 1fr; gap: 0.5rem; }
  .row-actions { justify-content: flex-end; }
  .banner { padding: 1.2rem; }
  .banner h2 { font-size: 1.1rem; }
}
</style>
