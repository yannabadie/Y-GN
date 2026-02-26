import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import { Dashboard } from "./pages/Dashboard";
import { GuardLog } from "./pages/GuardLog";
import { EvidenceViewer } from "./pages/EvidenceViewer";
import { NodeRegistry } from "./pages/NodeRegistry";
import { MemoryExplorer } from "./pages/MemoryExplorer";

function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen bg-gray-50">
        <nav className="w-56 bg-white border-r border-gray-200 p-4">
          <h2 className="text-lg font-bold mb-4 text-gray-800">Y-GN</h2>
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
