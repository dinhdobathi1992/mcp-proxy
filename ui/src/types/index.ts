export interface BackendStatus {
  name: string
  transport: string
  enabled: boolean
  health: 'healthy' | 'unhealthy' | 'unknown'
  requests: number
  errors: number
  latency_p50: number
  latency_p95: number
  latency_p99: number
  tools?: string[]
}

export interface StatusSnapshot {
  timestamp: string
  proxy_name: string
  backends: BackendStatus[]
  totals: {
    requests: number
    errors: number
    backends: number
    healthy: number
    unhealthy: number
  }
}
