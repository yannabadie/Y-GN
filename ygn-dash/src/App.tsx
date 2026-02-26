import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import { Dashboard } from "./pages/Dashboard";
import { GuardLog } from "./pages/GuardLog";
import { EvidenceViewer } from "./pages/EvidenceViewer";
import { NodeRegistry } from "./pages/NodeRegistry";
import { MemoryExplorer } from "./pages/MemoryExplorer";

function App() {
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const check = () => {
      fetch("http://localhost:3000/health")
        .then((r) => setConnected(r.ok))
        .catch(() => setConnected(false));
    };
    check();
    const interval = setInterval(check, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <BrowserRouter>
      <div className="flex h-screen bg-gray-50">
        <nav className="w-56 bg-white border-r border-gray-200 p-4">
          <div className="flex items-center gap-2 mb-4">
            <div className={`w-2 h-2 rounded-full ${connected ? "bg-green-500" : "bg-red-500"}`} />
            <h2 className="text-lg font-bold text-gray-800">Y-GN</h2>
          </div>
          <ul className="space-y-1">
            <li>
              <Link to="/" className="block px-3 py-2 rounded-md text-sm text-gray-700 hover:bg-gray-100">
                Dashboard
              </Link>
            </li>
            <li>
              <Link to="/guard" className="block px-3 py-2 rounded-md text-sm text-gray-700 hover:bg-gray-100">
                Guard Log
              </Link>
            </li>
            <li>
              <Link to="/evidence" className="block px-3 py-2 rounded-md text-sm text-gray-700 hover:bg-gray-100">
                Evidence
              </Link>
            </li>
            <li>
              <Link to="/nodes" className="block px-3 py-2 rounded-md text-sm text-gray-700 hover:bg-gray-100">
                Nodes
              </Link>
            </li>
            <li>
              <Link to="/memory" className="block px-3 py-2 rounded-md text-sm text-gray-700 hover:bg-gray-100">
                Memory
              </Link>
            </li>
          </ul>
        </nav>
        <main className="flex-1 overflow-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/guard" element={<GuardLog />} />
            <Route path="/evidence" element={<EvidenceViewer />} />
            <Route path="/nodes" element={<NodeRegistry />} />
            <Route path="/memory" element={<MemoryExplorer />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
