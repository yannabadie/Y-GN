# ygn-dash

Governance dashboard for Y-GN — visualizes evidence packs, guard decisions, memory tiers, and node registry.

## Tech Stack

- **Tauri 2** (Rust backend)
- **React 18** + TypeScript
- **Vite** (build tool)
- **Tailwind CSS v4**

## Pages

| Page | Description |
|------|-------------|
| Dashboard | Node status and evidence summaries |
| EvidenceViewer | Hash chain visualization and audit trail inspection |
| GuardLog | Security decision log with filtering |
| MemoryExplorer | 3-tier memory inspection (hot/warm/cold) |
| NodeRegistry | Network node discovery and status |

## Development

```bash
bun install
bun run tauri dev
```

## Build

```bash
bun run tauri build
```

## License

Apache-2.0
