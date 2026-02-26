import type {
  HealthResponse,
  ProvidersHealthResponse,
  GuardStats,
  RegistryNodesResponse,
  GuardLogResponse,
  SessionsResponse,
  MemoryStatsResponse,
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

export function fetchGuardLog() {
  return fetchJson<GuardLogResponse>("/guard/log");
}

export function fetchSessions() {
  return fetchJson<SessionsResponse>("/sessions");
}

export function fetchSession(id: string) {
  return fetchJson<Record<string, unknown>>(`/sessions/${id}`);
}

export function fetchMemoryStats() {
  return fetchJson<MemoryStatsResponse>("/memory/stats");
}
