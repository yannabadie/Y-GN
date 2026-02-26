interface TimelineEntry {
  id: string;
  timestamp: string;
  title: string;
  description: string;
  level: "none" | "low" | "medium" | "high" | "critical";
}

const levelColors = {
  none: "bg-gray-100 text-gray-700 border-gray-200",
  low: "bg-blue-100 text-blue-700 border-blue-200",
  medium: "bg-yellow-100 text-yellow-700 border-yellow-200",
  high: "bg-orange-100 text-orange-700 border-orange-200",
  critical: "bg-red-100 text-red-700 border-red-200",
};

const levelBadgeColors = {
  none: "bg-gray-200 text-gray-800",
  low: "bg-blue-200 text-blue-800",
  medium: "bg-yellow-200 text-yellow-800",
  high: "bg-orange-200 text-orange-800",
  critical: "bg-red-200 text-red-800",
};

interface TimelineProps {
  entries: TimelineEntry[];
}

export function Timeline({ entries }: TimelineProps) {
  if (entries.length === 0) {
    return (
      <p className="text-gray-500 text-sm">No guard events recorded yet.</p>
    );
  }

  return (
    <div className="space-y-3">
      {entries.map((entry) => (
        <div
          key={entry.id}
          className={`p-3 rounded-lg border ${levelColors[entry.level]}`}
        >
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">{entry.title}</span>
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2 py-0.5 rounded-full ${levelBadgeColors[entry.level]}`}>
                {entry.level.toUpperCase()}
              </span>
              <span className="text-xs opacity-60">{entry.timestamp}</span>
            </div>
          </div>
          {entry.description && (
            <p className="mt-1 text-xs opacity-75 truncate">{entry.description}</p>
          )}
        </div>
      ))}
    </div>
  );
}

export type { TimelineEntry };
