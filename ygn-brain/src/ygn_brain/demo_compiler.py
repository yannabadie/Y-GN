"""Demo: context compiler with artifact externalization.

Usage: ygn-brain-demo-compiler
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from .context_compiler.artifact_store import SqliteArtifactStore
from .context_compiler.processors import (
    ArtifactAttacher,
    Compactor,
    ContextCompiler,
    HistorySelector,
)
from .context_compiler.session import Session
from .context_compiler.token_budget import estimate_tokens
from .context_compiler.working_context import WorkingContext


def main() -> None:
    """Run the context compiler demo."""
    print("=" * 60)
    print("Y-GN Context Compiler Demo")
    print("=" * 60)

    # 1. Create session + artifact store
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "demo_artifacts.db"
    store = SqliteArtifactStore(db_path=db_path)
    print(f"\nArtifact store: {db_path}")

    session = Session()
    print(f"Session ID: {session.session_id}")

    # 2. Record user input
    user_input = "Analyze the system logs and summarize errors"
    session.record("user_input", {"text": user_input, "role": "user", "content": user_input}, token_estimate=15)

    # 3. Simulate a large tool output (10KB)
    large_output = "ERROR 2026-02-27 10:15:32 [worker-7] Connection timeout to db-primary\n" * 200
    large_tokens = estimate_tokens(large_output)
    print(f"\nSimulated tool output: {len(large_output)} bytes, ~{large_tokens} tokens")

    # 4. Compile without artifact attacher to show "before"
    compiler_no_artifacts = ContextCompiler(processors=[
        HistorySelector(keep_first=2, keep_last=3),
        Compactor(),
    ])

    ctx_before = compiler_no_artifacts.compile(
        session, budget=500, system_prompt="You are a log analysis assistant."
    )
    # Inject tool result to show what happens without externalization
    ctx_before_with_tool = WorkingContext(
        system_prompt=ctx_before.system_prompt,
        history=ctx_before.history,
        memory_hits=ctx_before.memory_hits,
        artifact_refs=ctx_before.artifact_refs,
        tool_results=[{"tool": "log_reader", "result": large_output}],
        token_count=ctx_before.token_count + large_tokens,
        budget=500,
    )

    print(f"\n--- BEFORE externalization ---")
    print(f"Token count: {ctx_before_with_tool.token_count}")
    print(f"Within budget (500): {ctx_before_with_tool.is_within_budget()}")
    print(f"Overflow: {ctx_before_with_tool.overflow()} tokens")
    print(f"Tool results in prompt: {len(ctx_before_with_tool.tool_results)}")
    print(f"Artifact refs: {len(ctx_before_with_tool.artifact_refs)}")

    # 5. Run ArtifactAttacher on the bloated context
    attacher = ArtifactAttacher(artifact_store=store, threshold_bytes=1024)
    ctx_after = attacher.process(session, ctx_before_with_tool, budget=500)

    print(f"\n--- AFTER externalization ---")
    print(f"Token count: {ctx_after.token_count}")
    print(f"Within budget (500): {ctx_after.is_within_budget()}")
    print(f"Overflow: {ctx_after.overflow()} tokens")
    print(f"Tool results in prompt: {len(ctx_after.tool_results)}")
    print(f"Artifact refs: {len(ctx_after.artifact_refs)}")

    if ctx_after.artifact_refs:
        ref = ctx_after.artifact_refs[0]
        print(f"\n  Handle:  {ref['handle'][:16]}...")
        print(f"  Summary: {ref['summary'][:80]}...")
        print(f"  Size:    {ref['size_bytes']} bytes")

        # Verify retrieval
        data = store.retrieve(ref["handle"])
        if data:
            print(f"  Retrieved: {len(data)} bytes (matches: {data == large_output.encode()})")

    # 6. Show the compiled messages
    messages = ctx_after.to_messages()
    print(f"\n--- Compiled messages for LLM ({len(messages)} total) ---")
    for i, msg in enumerate(messages):
        content = msg["content"]
        if len(content) > 200:
            content = content[:200] + "..."
        print(f"  [{i}] {msg['role']}: {content}")

    print(f"\n{'=' * 60}")
    print("Demo complete. Large tool output externalized, handle in prompt.")
    print(f"{'=' * 60}")

    store.close()


if __name__ == "__main__":
    main()
