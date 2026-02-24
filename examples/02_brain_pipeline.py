#!/usr/bin/env python3
"""02_brain_pipeline.py — Y-GN Brain orchestration demo.

Demonstrates running a user query through the Brain's 7-phase HiveMind
pipeline and inspecting the result along with the Evidence Pack session ID.

The provider is selected via YGN_LLM_PROVIDER (codex | gemini | stub).
Default: stub (deterministic, no external calls).

Prerequisites:
    - ygn-brain installed (see INSTALL.md, step 4)
      pip install -e ygn-brain/.[dev]

Usage:
    python examples/02_brain_pipeline.py
    YGN_LLM_PROVIDER=codex python examples/02_brain_pipeline.py
"""

from __future__ import annotations

from ygn_brain import Orchestrator, ProviderFactory


def main() -> None:
    # ------------------------------------------------------------------
    # 1. Create an Orchestrator instance.
    #    The provider is resolved via ProviderFactory based on
    #    YGN_LLM_PROVIDER env var (default: stub).
    # ------------------------------------------------------------------
    provider = ProviderFactory.create()
    print(f"Provider: {ProviderFactory.describe(provider)}")
    orchestrator = Orchestrator(provider=provider)

    # ------------------------------------------------------------------
    # 2. Define a query and run it through the pipeline.
    #    The pipeline phases are:
    #      Diagnosis -> Analysis -> Planning -> Execution ->
    #      Validation -> Synthesis -> Complete
    # ------------------------------------------------------------------
    query = "What are the security implications of running untrusted WASM modules?"
    print(f"Query: {query}")
    print()

    result = orchestrator.run(query)

    # ------------------------------------------------------------------
    # 3. Inspect the result.
    #    - result["result"]     : the synthesized answer
    #    - result["session_id"] : unique ID for this Evidence Pack session
    # ------------------------------------------------------------------
    print("--- Pipeline Result ---")
    print(f"Result:     {result['result']}")
    print(f"Session ID: {result['session_id']}")

    # Check if the input was blocked by the guard pipeline
    if result.get("blocked"):
        print("Note: the query was blocked by the guard pipeline.")

    # ------------------------------------------------------------------
    # 4. The Evidence Pack is also available on the orchestrator instance.
    #    It records every guard decision, phase output, and tool call
    #    for full auditability.
    # ------------------------------------------------------------------
    print()
    print(f"Evidence Pack entries: {len(orchestrator.evidence.entries)}")
    for entry in orchestrator.evidence.entries:
        print(f"  [{entry.phase}] {entry.kind}: {entry.data}")


if __name__ == "__main__":
    main()
