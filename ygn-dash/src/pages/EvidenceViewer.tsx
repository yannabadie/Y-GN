import { useEffect, useState } from "react";
import { fetchSessions, fetchSession } from "../lib/api";
import type { SessionInfo } from "../lib/types";
import { HashChainView } from "../components/HashChainView";
import type { HashEntry } from "../components/HashChainView";

export function EvidenceViewer() {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [entries, setEntries] = useState<HashEntry[]>([]);

  useEffect(() => {
    fetchSessions()
      .then((data) => setSessions(data.sessions))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedSession) {
      setEntries([]);
      return;
    }
    fetchSession(selectedSession)
      .then((data) => {
        const raw = (data.entries ?? []) as HashEntry[];
        setEntries(raw);
      })
      .catch(() => setEntries([]));
  }, [selectedSession]);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4 text-gray-900">Evidence Viewer</h1>

      {!selectedSession ? (
        <div>
          <h2 className="text-lg font-semibold mb-3 text-gray-800">Sessions</h2>
          <div className="space-y-2">
            {sessions.length === 0 && (
              <p className="text-gray-500 text-sm">No sessions recorded yet.</p>
            )}
            {sessions.map((s) => (
              <button
                key={s.id}
                onClick={() => setSelectedSession(s.id)}
                className="w-full text-left p-3 rounded-lg border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-sm">{s.id}</span>
                  <span className="text-xs text-gray-500">{s.entry_count} entries</span>
                </div>
                <div className="mt-1 text-xs text-gray-500">
                  Model: {s.model} | {new Date(s.timestamp).toLocaleString()}
                </div>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div>
          <button
            onClick={() => setSelectedSession(null)}
            className="mb-4 text-sm text-blue-600 hover:text-blue-800"
          >
            &larr; Back to sessions
          </button>
          <h2 className="text-lg font-semibold mb-3 text-gray-800">
            Session: {selectedSession}
          </h2>
          <HashChainView entries={entries} />
        </div>
      )}
    </div>
  );
}
