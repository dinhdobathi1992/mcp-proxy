<script setup lang="ts">
import { computed } from 'vue'
import type { StatusSnapshot } from '../types'
import BackendCard from './BackendCard.vue'

const props = defineProps<{ data: StatusSnapshot | null; connected: boolean }>()

const totals = computed(() => props.data?.totals ?? null)

const errorRate = computed(() => {
  if (!totals.value || totals.value.requests === 0) return 0
  return (totals.value.errors / totals.value.requests) * 100
})

const healthRatio = computed(() => {
  if (!totals.value || totals.value.backends === 0) return 0
  return (totals.value.healthy / totals.value.backends) * 100
})

const sortedBackends = computed(() => {
  if (!props.data) return []
  const order = { unhealthy: 0, unknown: 1, healthy: 2 } as const
  return [...props.data.backends].sort((a, b) => {
    const oa = order[a.health as keyof typeof order] ?? 3
    const ob = order[b.health as keyof typeof order] ?? 3
    if (oa !== ob) return oa - ob
    return b.requests - a.requests
  })
})
</script>

<template>
  <div class="dashboard">
    <!-- Empty state -->
    <div v-if="!data" class="empty">
      <div class="spinner"></div>
      <div class="empty-title">Awaiting telemetry</div>
      <div class="empty-sub">{{ connected ? 'Connected — waiting for first snapshot…' : 'Establishing connection to /ws…' }}</div>
    </div>

    <template v-else>
      <!-- Summary stats -->
      <div class="summary">
        <div class="stat-card stat-primary">
          <div class="stat-head">
            <span class="stat-label">Backends</span>
            <span class="stat-icon">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="2" y="2" width="20" height="8" rx="2"/>
                <rect x="2" y="14" width="20" height="8" rx="2"/>
                <line x1="6" y1="6" x2="6.01" y2="6"/>
                <line x1="6" y1="18" x2="6.01" y2="18"/>
              </svg>
            </span>
          </div>
          <div class="stat-value">{{ totals?.backends ?? 0 }}</div>
          <div class="stat-foot">
            <span class="trend-bar">
              <span class="trend-fill" :style="{ width: healthRatio + '%' }"></span>
            </span>
            <span class="stat-trend">{{ healthRatio.toFixed(0) }}% online</span>
          </div>
        </div>

        <div class="stat-card stat-ok">
          <div class="stat-head">
            <span class="stat-label">Healthy</span>
            <span class="stat-icon">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                <polyline points="22 4 12 14.01 9 11.01"/>
              </svg>
            </span>
          </div>
          <div class="stat-value">{{ totals?.healthy ?? 0 }}</div>
          <div class="stat-foot">
            <span class="pill pill-ok" v-if="(totals?.unhealthy ?? 0) === 0">all systems nominal</span>
            <span class="pill pill-err" v-else>{{ totals?.unhealthy }} down</span>
          </div>
        </div>

        <div class="stat-card stat-info">
          <div class="stat-head">
            <span class="stat-label">Requests</span>
            <span class="stat-icon">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
                <polyline points="17 6 23 6 23 12"/>
              </svg>
            </span>
          </div>
          <div class="stat-value">{{ (totals?.requests ?? 0).toLocaleString() }}</div>
          <div class="stat-foot">
            <span class="stat-trend">total since boot</span>
          </div>
        </div>

        <div class="stat-card" :class="errorRate > 1 ? 'stat-err' : 'stat-muted'">
          <div class="stat-head">
            <span class="stat-label">Errors</span>
            <span class="stat-icon">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
            </span>
          </div>
          <div class="stat-value">{{ (totals?.errors ?? 0).toLocaleString() }}</div>
          <div class="stat-foot">
            <span class="pill" :class="errorRate > 1 ? 'pill-err' : 'pill-muted'">
              {{ errorRate.toFixed(2) }}% rate
            </span>
          </div>
        </div>
      </div>

      <!-- Backends grid -->
      <div class="section-head">
        <h2>Backends</h2>
        <div class="legend">
          <span class="leg"><span class="leg-dot leg-ok"></span>healthy</span>
          <span class="leg"><span class="leg-dot leg-warn"></span>unknown</span>
          <span class="leg"><span class="leg-dot leg-err"></span>unhealthy</span>
        </div>
      </div>

      <div v-if="sortedBackends.length === 0" class="no-backends">
        <span>No backends configured.</span>
      </div>

      <div v-else class="backends">
        <BackendCard
          v-for="backend in sortedBackends"
          :key="backend.name"
          :backend="backend"
        />
      </div>
    </template>
  </div>
</template>

<style scoped>
.dashboard { max-width: 1280px; margin: 0 auto; }

/* Empty / loading ---------------------------------------- */
.empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  min-height: 50vh; gap: 0.6rem; text-align: center;
}
.spinner {
  width: 32px; height: 32px; border-radius: 50%;
  border: 2px solid var(--border-2); border-top-color: var(--accent);
  animation: spin 0.9s linear infinite;
  margin-bottom: 0.5rem;
}
.empty-title { font-weight: 600; color: var(--text-1); }
.empty-sub { color: var(--text-3); font-size: 0.85rem; }

@keyframes spin { to { transform: rotate(360deg); } }

/* Stat cards --------------------------------------------- */
.summary {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem;
  margin-bottom: 2rem;
}

.stat-card {
  position: relative;
  padding: 1.1rem 1.15rem;
  background: var(--surface-card);
  border: 1px solid var(--border-1);
  border-radius: var(--radius-lg);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  overflow: hidden;
  transition: transform 200ms ease, border-color 200ms ease, background 200ms ease;
}
.stat-card::before {
  content: ''; position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(280px 120px at 100% 0%, var(--card-glow, transparent), transparent 60%);
  opacity: 0.7;
}
.stat-card:hover { transform: translateY(-1px); border-color: var(--border-2); }

.stat-primary { --card-glow: rgba(124, 92, 255, 0.18); }
.stat-ok      { --card-glow: rgba(52, 211, 153, 0.18); }
.stat-info    { --card-glow: rgba(0, 212, 255, 0.18); }
.stat-err     { --card-glow: rgba(251, 113, 133, 0.22); }
.stat-muted   { --card-glow: rgba(255, 255, 255, 0.04); }

.stat-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.6rem; }
.stat-label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.12em; color: var(--text-4); font-weight: 600; }
.stat-icon {
  width: 26px; height: 26px;
  display: grid; place-items: center;
  border-radius: 7px;
  background: var(--surface-glass);
  border: 1px solid var(--border-1);
  color: var(--text-3);
}
.stat-primary .stat-icon { color: var(--accent); border-color: rgba(124, 92, 255, 0.25); background: var(--accent-soft); }
.stat-ok .stat-icon { color: var(--ok); border-color: rgba(52, 211, 153, 0.25); background: var(--ok-soft); }
.stat-info .stat-icon { color: var(--info); border-color: rgba(96, 165, 250, 0.25); background: var(--info-soft); }
.stat-err .stat-icon { color: var(--err); border-color: rgba(251, 113, 133, 0.3); background: var(--err-soft); }

.stat-value {
  font-size: 2.4rem; font-weight: 600; letter-spacing: -0.03em;
  color: var(--text-1); line-height: 1.05;
  font-variant-numeric: tabular-nums;
  font-feature-settings: 'tnum';
}
.stat-foot { margin-top: 0.7rem; display: flex; align-items: center; gap: 0.55rem; flex-wrap: wrap; }
.stat-trend { font-size: 0.74rem; color: var(--text-3); }

.trend-bar {
  position: relative; flex: 1; max-width: 80px; height: 4px;
  background: var(--border-1); border-radius: 2px; overflow: hidden;
}
.trend-fill {
  position: absolute; inset: 0; right: auto;
  background: var(--grad-ok);
  border-radius: 2px;
  transition: width 400ms cubic-bezier(0.2, 0.7, 0.2, 1);
}

.pill {
  display: inline-flex; align-items: center;
  font-size: 0.7rem; font-weight: 500;
  padding: 2px 8px; border-radius: 999px;
  border: 1px solid transparent;
  letter-spacing: 0.01em;
}
.pill-ok    { background: var(--ok-soft); color: var(--ok); border-color: rgba(52, 211, 153, 0.25); }
.pill-err   { background: var(--err-soft); color: var(--err); border-color: rgba(251, 113, 133, 0.3); }
.pill-muted { background: var(--surface-glass); color: var(--text-3); border-color: var(--border-1); }

/* Section ------------------------------------------------ */
.section-head {
  display: flex; align-items: center; justify-content: space-between;
  margin: 0.5rem 0 1rem;
}
.section-head h2 {
  font-size: 0.95rem; font-weight: 600; letter-spacing: -0.01em;
  color: var(--text-2);
}
.legend { display: flex; align-items: center; gap: 0.85rem; font-size: 0.72rem; color: var(--text-4); }
.leg { display: inline-flex; align-items: center; gap: 0.4rem; }
.leg-dot { width: 7px; height: 7px; border-radius: 50%; }
.leg-ok { background: var(--ok); box-shadow: 0 0 8px rgba(52, 211, 153, 0.6); }
.leg-warn { background: var(--warn); box-shadow: 0 0 8px rgba(251, 191, 36, 0.6); }
.leg-err { background: var(--err); box-shadow: 0 0 8px rgba(251, 113, 133, 0.6); }

.backends {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1rem;
}
.no-backends {
  padding: 2rem; text-align: center;
  color: var(--text-3); font-size: 0.9rem;
  border: 1px dashed var(--border-2); border-radius: var(--radius-lg);
}

/* Responsive --------------------------------------------- */
@media (max-width: 1100px) { .summary { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 600px) {
  .summary { grid-template-columns: 1fr 1fr; gap: 0.75rem; }
  .stat-value { font-size: 1.9rem; }
  .legend { display: none; }
  .backends { grid-template-columns: 1fr; }
}
</style>
