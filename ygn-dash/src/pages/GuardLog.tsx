import { useEffect, useState } from "react";
import { fetchGuardLog } from "../lib/api";
import type { GuardLogEntry } from "../lib/types";
import { Timeline } from "../components/Timeline";
import type { TimelineEntry } from "../components/Timeline";

type FilterLevel = "all" | "none" | "low" | "medium" | "high" | "critical";

function toTimelineEntry(e: GuardLogEntry): TimelineEntry {
  const levelMap: Record<string, TimelineEntry["level"]> = {
    none: "none",
    low: "low",
    medium: "medium",
    high: "high",
    critical: "critical",
  };
  return {
    id: e.id,
    timestamp: e.timestamp,
    title: e.allowed ? "Clean input" : `Blocked: ${e.reason}`,
    description: e.input_preview,
    level: levelMap[e.threat_level] ?? "none",
  };
}

export function GuardLog() {
  const [entries, setEntries] = useState<GuardLogEntry[]>([]);
  const [filter, setFilter] = useState<FilterLevel>("all");

  useEffect(() => {
    const refresh = () => {
      fetchGuardLog()
        .then((data) => setEntries(data.entries))
        .catch(() => {});
    };
    refresh();
    const interval = setInterval(refresh, 10000);
    return () => clearInterval(interval);
  }, []);

  const timelineEntries = entries.map(toTimelineEntry);

  const filteredEntries = filter === "all"
    ? timelineEntries
    : timelineEntries.filter((e) => e.level === filter);

  const filters: FilterLevel[] = ["all", "none", "low", "medium", "high", "critical"];

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4 text-gray-900">Guard Log</h1>

      <div className="flex gap-2 mb-4">
        {filters.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded-md text-sm ${
              filter === f
                ? "bg-gray-900 text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            {f === "all" ? "All" : f.toUpperCase()}
          </button>
        ))}
      </div>

      <Timeline entries={filteredEntries} />
    </div>
  );
}
