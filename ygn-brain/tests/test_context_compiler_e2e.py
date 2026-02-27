"""E2E tests for the full context compiler pipeline."""

import tempfile
from pathlib import Path

from ygn_brain.context_compiler.artifact_store import SqliteArtifactStore
from ygn_brain.context_compiler.processors import (
    ArtifactAttacher,
    Compactor,
    ContextCompiler,
    HistorySelector,
)
from ygn_brain.context_compiler.session import Session
from ygn_brain.context_compiler.working_context import WorkingContext


def test_large_payload_externalized():
    """Verify that a large tool output is externalized to ArtifactStore
    and replaced with a handle in the WorkingContext."""
    tmpdir = tempfile.mkdtemp()
    store = SqliteArtifactStore(db_path=Path(tmpdir) / "art.db")

    try:
        session = Session()
        session.record("user_input", {"text": "Analyze this file"}, token_estimate=10)

        # Simulate pipeline: first compile to get base context, then manually
        # attach a large tool result and run ArtifactAttacher
        compiler = ContextCompiler(processors=[
            HistorySelector(keep_first=2, keep_last=3),
            Compactor(),
        ])
        base_ctx = compiler.compile(session, budget=500, system_prompt="You are helpful.")

        # Add a large tool result to the context (simulating what would come from ToolInterruptHandler)
        large_output = " ".join(["error_log_line"] * 2000)  # ~2000 words, ~2600 tokens, ~30KB
        from ygn_brain.context_compiler.token_budget import estimate_tokens
        tool_tokens = estimate_tokens(large_output)

        ctx_with_tool = WorkingContext(
            system_prompt=base_ctx.system_prompt,
            history=base_ctx.history,
            memory_hits=base_ctx.memory_hits,
            artifact_refs=base_ctx.artifact_refs,
            tool_results=[{"tool": "log_reader", "result": large_output}],
            token_count=base_ctx.token_count + tool_tokens,
            budget=500,
        )

        # Before: way over budget
        assert not ctx_with_tool.is_within_budget()
        assert ctx_with_tool.overflow() > 0

        # Run ArtifactAttacher
        attacher = ArtifactAttacher(artifact_store=store, threshold_bytes=1024)
        ctx_after = attacher.process(session, ctx_with_tool, budget=500)

        # After: tool result externalized
        assert len(ctx_after.tool_results) == 0  # large result removed
        assert len(ctx_after.artifact_refs) >= 1  # replaced with artifact ref
        assert ctx_after.artifact_refs[0]["handle"]  # has a handle
        assert ctx_after.artifact_refs[0]["size_bytes"] > 0

        # Token count drastically reduced
        assert ctx_after.token_count < ctx_with_tool.token_count

        # Can retrieve the artifact by handle
        data = store.retrieve(ctx_after.artifact_refs[0]["handle"])
        assert data is not None
        assert len(data) > 0

    finally:
        store.close()


def test_budget_respected():
    """Verify that the compiled WorkingContext respects the token budget
    by trimming history via HistorySelector."""
    session = Session()
    # Alternate user_input and phase_result to simulate real conversation turns.
    # HistorySelector picks from these two event kinds; Compactor won't merge
    # them because they alternate between "user" and "assistant" roles.
    for i in range(50):
        if i % 2 == 0:
            session.record(
                "user_input",
                {"role": "user", "content": f"User message {i} with some content padding"},
                token_estimate=15,
            )
        else:
            session.record(
                "phase_result",
                {"role": "assistant", "content": f"Assistant reply {i} with some content"},
                token_estimate=15,
            )

    compiler = ContextCompiler(processors=[
        HistorySelector(keep_first=2, keep_last=3),
        Compactor(),
    ])

    ctx = compiler.compile(session, budget=200, system_prompt="Short prompt.")
    # HistorySelector keeps first 2 + last 3 = 5 messages from 50.
    # Compactor then merges consecutive same-role messages at the splice boundary
    # (message [1]=assistant and [47]=assistant become adjacent after trimming),
    # yielding 4 messages: user, assistant(merged), user, assistant.
    assert len(ctx.history) == 4
    # History was drastically trimmed from 50 events
    assert len(ctx.history) < 50
    # Token count should be reasonable (not 50*15=750)
    assert ctx.token_count < 200
    # Verify the pipeline preserved conversation structure
    assert ctx.history[0]["role"] == "user"
    assert ctx.history[-1]["role"] == "assistant"
