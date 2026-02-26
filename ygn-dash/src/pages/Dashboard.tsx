import { useEffect, useState } from "react";
import { StatusCard } from "../components/StatusCard";
import { fetchHealth, fetchProvidersHealth, fetchGuardStats } from "../lib/api";
import type { HealthResponse, ProvidersHealthResponse, GuardStats } from "../lib/types";

export function Dashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [providers, setProviders] = useState<ProvidersHealthResponse | null>(null);
  const [guardStats, setGuardStats] = useState<GuardStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setError("Core offline"));
    fetchProvidersHealth().then(setProviders).catch(() => {});
    fetchGuardStats().then(setGuardStats).catch(() => {});
  }, []);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6 text-gray-900">Y-GN Governance Dashboard</h1>

      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-md text-sm">
          {error} — Make sure ygn-core gateway is running on localhost:3000
        </div>
      )}

      <div className="grid grid-cols-4 gap-4 mb-8">
        <StatusCard
          title="Core Status"
          value={health ? "Online" : "Offline"}
          status={health ? "ok" : "error"}
          subtitle={health?.version}
        />
        <StatusCard
          title="Guard Checks"
          value={guardStats?.total_checks ?? 0}
          status={(guardStats?.blocked ?? 0) > 0 ? "warning" : "ok"}
          subtitle={`${guardStats?.blocked ?? 0} blocked`}
        />
        <StatusCard
          title="Providers"
          value={providers?.providers?.length ?? 0}
          status={providers?.status === "ok" ? "ok" : "warning"}
          subtitle={providers?.status ?? "unknown"}
        />
        <StatusCard
          title="Version"
          value={health?.version ?? "\u2014"}
          status="ok"
          subtitle="ygn-core"
        />
      </div>

      {providers && providers.providers.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-3 text-gray-800">Provider Health</h2>
          <div className="grid grid-cols-3 gap-3">
            {providers.providers.map((p) => (
              <div
                key={p.provider}
                className={`p-3 rounded-lg border ${
                  p.healthy ? "border-green-200 bg-green-50" : "border-red-200 bg-red-50"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-sm">{p.provider}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    p.healthy ? "bg-green-200 text-green-800" : "bg-red-200 text-red-800"
                  }`}>
                    {p.healthy ? "Healthy" : "Unhealthy"}
                  </span>
                </div>
                <div className="mt-2 text-xs text-gray-600">
                  <span>Requests: {p.total_requests}</span>
                  <span className="ml-3">Latency: {p.avg_latency_ms.toFixed(1)}ms</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
