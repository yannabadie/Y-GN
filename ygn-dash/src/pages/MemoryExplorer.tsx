import { useState } from "react";
import { TierChart } from "../components/TierChart";

export function MemoryExplorer() {
  const [searchQuery, setSearchQuery] = useState("");
  const [searchMode, setSearchMode] = useState<"bm25" | "semantic">("bm25");

  // Mock data
  const tierData = { hot: 24, warm: 156, cold: 892 };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4 text-gray-900">Memory Explorer</h1>

      <div className="grid grid-cols-2 gap-6 mb-6">
        <div className="p-4 rounded-lg border border-gray-200 bg-white">
          <h2 className="text-lg font-semibold mb-2 text-gray-800">Tier Distribution</h2>
          <TierChart hot={tierData.hot} warm={tierData.warm} cold={tierData.cold} />
        </div>
        <div className="p-4 rounded-lg border border-gray-200 bg-white">
          <h2 className="text-lg font-semibold mb-2 text-gray-800">Statistics</h2>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Hot entries</span>
              <span className="font-medium">{tierData.hot}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Warm entries</span>
              <span className="font-medium">{tierData.warm}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Cold entries</span>
              <span className="font-medium">{tierData.cold}</span>
            </div>
            <div className="flex justify-between border-t pt-2">
              <span className="text-gray-600 font-medium">Total</span>
              <span className="font-bold">
                {tierData.hot + tierData.warm + tierData.cold}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="mb-4">
        <div className="flex gap-2 items-center">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search memory..."
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <div className="flex rounded-md border border-gray-300">
            <button
              onClick={() => setSearchMode("bm25")}
              className={`px-3 py-2 text-sm ${
                searchMode === "bm25" ? "bg-gray-900 text-white" : "bg-white text-gray-700"
              } rounded-l-md`}
            >
              BM25
            </button>
            <button
              onClick={() => setSearchMode("semantic")}
              className={`px-3 py-2 text-sm ${
                searchMode === "semantic" ? "bg-gray-900 text-white" : "bg-white text-gray-700"
              } rounded-r-md`}
            >
              Semantic
            </button>
          </div>
        </div>
      </div>

      <p className="text-gray-500 text-sm">
        Search results will appear here when connected to ygn-core.
      </p>
    </div>
  );
}
