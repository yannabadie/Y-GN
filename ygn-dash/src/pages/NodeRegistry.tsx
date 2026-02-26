import { useEffect, useState } from "react";
import { fetchRegistryNodes } from "../lib/api";
import type { NodeInfo } from "../lib/types";

export function NodeRegistry() {
  const [nodes, setNodes] = useState<NodeInfo[]>([]);
  const [roleFilter, setRoleFilter] = useState<string>("all");

  useEffect(() => {
    fetchRegistryNodes()
      .then((data) => setNodes(data.nodes))
      .catch(() => {});
  }, []);

  const filteredNodes =
    roleFilter === "all" ? nodes : nodes.filter((n) => n.role === roleFilter);

  const roles = ["all", "brain", "core", "edge", "brain_proxy"];

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4 text-gray-900">Node Registry</h1>

      <div className="flex gap-2 mb-4">
        {roles.map((r) => (
          <button
            key={r}
            onClick={() => setRoleFilter(r)}
            className={`px-3 py-1 rounded-md text-sm ${
              roleFilter === r
                ? "bg-gray-900 text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            {r === "all" ? "All" : r.charAt(0).toUpperCase() + r.slice(1)}
          </button>
        ))}
      </div>

      {filteredNodes.length === 0 ? (
        <p className="text-gray-500 text-sm">
          No nodes registered. Start ygn-core gateway to see nodes.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-2 px-3 font-medium text-gray-600">Node ID</th>
                <th className="text-left py-2 px-3 font-medium text-gray-600">Role</th>
                <th className="text-left py-2 px-3 font-medium text-gray-600">Trust</th>
                <th className="text-left py-2 px-3 font-medium text-gray-600">Capabilities</th>
                <th className="text-left py-2 px-3 font-medium text-gray-600">Last Seen</th>
              </tr>
            </thead>
            <tbody>
              {filteredNodes.map((node) => (
                <tr key={node.node_id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="py-2 px-3 font-mono text-xs">{node.node_id.slice(0, 8)}...</td>
                  <td className="py-2 px-3">
                    <span className="px-2 py-0.5 rounded-full text-xs bg-blue-100 text-blue-800">
                      {node.role}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-xs">{node.trust_tier}</td>
                  <td className="py-2 px-3 text-xs">{node.capabilities.join(", ")}</td>
                  <td className="py-2 px-3 text-xs text-gray-500">
                    {new Date(node.last_seen).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
