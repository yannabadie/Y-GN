import type {
  HealthResponse,
  ProvidersHealthResponse,
  GuardStats,
  RegistryNodesResponse,
} from "./types";

const BASE_URL = "http://localhost:3000";

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${path}`);
  return res.json();
}

export function fetchHealth() {
  return fetchJson<HealthResponse>("/health");
}

export function fetchProvidersHealth() {
  return fetchJson<ProvidersHealthResponse>("/health/providers");
}

export function fetchGuardStats() {
  return fetchJson<GuardStats>("/guard/stats");
}

export function fetchRegistryNodes() {
  return fetchJson<RegistryNodesResponse>("/registry/nodes");
}
