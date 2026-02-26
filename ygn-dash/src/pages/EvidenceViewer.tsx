import { useState } from "react";
import { HashChainView } from "../components/HashChainView";
import type { HashEntry } from "../components/HashChainView";

// Mock evidence data for demonstration
const mockSessions = [
  {
    id: "sess-001",
    model: "gpt-5.2-codex",
    entries: 7,
    timestamp: "2026-02-26T10:30:00Z",
  },
  {
    id: "sess-002",
    model: "gemini-2.5-pro",
    entries: 5,
    timestamp: "2026-02-26T11:15:00Z",
  },
];

const mockEntries: HashEntry[] = [
  {
    entry_id: "e001",
    entry_hash: "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
    prev_hash: "",
    phase: "diagnosis",
    kind: "input",
    timestamp: Date.now() / 1000 - 300,
    signature: "ed25519:abc123",
  },
  {
    entry_id: "e002",
    entry_hash: "b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5",
    prev_hash: "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
    phase: "analysis",
    kind: "decision",
    timestamp: Date.now() / 1000 - 200,
    signature: "ed25519:def456",
  },
  {
    entry_id: "e003",
    entry_hash: "c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6",
    prev_hash: "b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5",
    phase: "execution",
    kind: "tool_call",
    timestamp: Date.now() / 1000 - 100,
    signature: "",
  },
];

export function EvidenceViewer() {
  const [selectedSession, setSelectedSession] = useState<string | null>(null);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4 text-gray-900">Evidence Viewer</h1>

      {!selectedSession ? (
        <div>
          <h2 className="text-lg font-semibold mb-3 text-gray-800">Sessions</h2>
          <div className="space-y-2">
            {mockSessions.map((s) => (
              <button
                key={s.id}
                onClick={() => setSelectedSession(s.id)}
                className="w-full text-left p-3 rounded-lg border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-sm">{s.id}</span>
                  <span className="text-xs text-gray-500">{s.entries} entries</span>
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
          <HashChainView entries={mockEntries} />
        </div>
      )}
    </div>
  );
}
