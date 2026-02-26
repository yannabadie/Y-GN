export interface ProviderStatus {
  provider: string;
  healthy: boolean;
  consecutive_failures: number;
  total_requests: number;
  total_failures: number;
  avg_latency_ms: number;
}

export interface GuardStats {
  total_checks: number;
  blocked: number;
  threat_levels: Record<string, number>;
  avg_latency_ms: number;
}

export interface NodeInfo {
  node_id: string;
  role: string;
  trust_tier: string;
  endpoints: { protocol: string; address: string }[];
  capabilities: string[];
  last_seen: string;
}

export interface EvidenceEntry {
  timestamp: number;
  phase: string;
  kind: string;
  data: Record<string, unknown>;
  entry_id: string;
  entry_hash: string;
  prev_hash: string;
  signature: string;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export interface ProvidersHealthResponse {
  status: string;
  providers: ProviderStatus[];
}

export interface RegistryNodesResponse {
  nodes: NodeInfo[];
  count: number;
}
