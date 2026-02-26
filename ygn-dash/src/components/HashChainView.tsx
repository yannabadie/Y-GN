interface HashEntry {
  entry_id: string;
  entry_hash: string;
  prev_hash: string;
  phase: string;
  kind: string;
  timestamp: number;
  signature: string;
}

interface HashChainViewProps {
  entries: HashEntry[];
}

export function HashChainView({ entries }: HashChainViewProps) {
  if (entries.length === 0) {
    return <p className="text-gray-500 text-sm">No evidence entries.</p>;
  }

  return (
    <div className="space-y-2">
      {entries.map((entry, i) => {
        const isFirst = i === 0;
        const hashMatch = isFirst
          ? entry.prev_hash === ""
          : entry.prev_hash === entries[i - 1].entry_hash;

        return (
          <div key={entry.entry_id} className="flex items-start gap-3">
            <div className="flex flex-col items-center">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                hashMatch ? "bg-green-200 text-green-800" : "bg-red-200 text-red-800"
              }`}>
                {hashMatch ? "\u2713" : "\u2717"}
              </div>
              {i < entries.length - 1 && (
                <div className="w-0.5 h-8 bg-gray-300 mt-1" />
              )}
            </div>
            <div className="flex-1 p-2 rounded border border-gray-200 bg-white">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">{entry.phase} / {entry.kind}</span>
                <div className="flex items-center gap-2">
                  {entry.signature && (
                    <span className="text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded">
                      signed
                    </span>
                  )}
                  <span className="text-xs text-gray-400">
                    {new Date(entry.timestamp * 1000).toLocaleTimeString()}
                  </span>
                </div>
              </div>
              <div className="mt-1 font-mono text-xs text-gray-500 truncate">
                hash: {entry.entry_hash.slice(0, 16)}...
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export type { HashEntry };
