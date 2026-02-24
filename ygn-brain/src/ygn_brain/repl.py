"""Interactive REPL for the Y-GN Brain pipeline."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from .orchestrator import Orchestrator
from .provider_factory import ProviderFactory


def main() -> None:
    """Entry point for ``ygn-brain-repl`` command (synchronous).

    Uses :class:`ProviderFactory` to select the provider based on
    ``YGN_LLM_PROVIDER`` env var.  Sync mode always uses stub because
    the CLI providers require async I/O.
    """
    print("Y-GN Brain REPL v0.1.0")
    print("Type 'quit' or 'exit' to exit, 'status' for pipeline info")
    print("Using StubLLMProvider (sync mode — use --async for CLI providers)")
    print()

    orchestrator = Orchestrator()

    while True:
        try:
            user_input = input("ygn> ")
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        stripped = user_input.strip()
        if not stripped:
            continue
        if stripped in ("quit", "exit"):
            print("Bye!")
            break
        if stripped == "status":
            print(f"  FSM state: {orchestrator.state.phase}")
            print(f"  Session: {orchestrator.evidence.session_id}")
            print(f"  Evidence entries: {len(orchestrator.evidence.entries)}")
            continue
        if stripped == "help":
            print("Commands: status, help, quit/exit")
            print("Anything else is processed as a task through the pipeline")
            continue

        # Run through orchestrator (sync uses stub pipeline)
        result = orchestrator.run(stripped)
        _print_result(result)


async def async_main() -> None:
    """Async entry point — uses the provider resolved by ProviderFactory.

    Set ``YGN_LLM_PROVIDER`` to ``codex``, ``gemini``, or ``stub``.
    """
    provider = ProviderFactory.create()
    desc = ProviderFactory.describe(provider)

    print("Y-GN Brain REPL v0.1.0 (async)")
    print(f"Provider: {desc}")
    print("Type 'quit' or 'exit' to exit, 'status' for pipeline info")
    print()

    orchestrator = Orchestrator(provider=provider)

    while True:
        try:
            user_input = input("ygn> ")
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        stripped = user_input.strip()
        if not stripped:
            continue
        if stripped in ("quit", "exit"):
            print("Bye!")
            break
        if stripped == "status":
            print(f"  FSM state: {orchestrator.state.phase}")
            print(f"  Session: {orchestrator.evidence.session_id}")
            print(f"  Evidence entries: {len(orchestrator.evidence.entries)}")
            continue
        if stripped == "help":
            print("Commands: status, help, quit/exit")
            print("Anything else is processed as a task through the pipeline (async)")
            continue

        result = await orchestrator.run_async(stripped)
        _print_result(result)


def _print_result(result: dict[str, Any]) -> None:
    """Format and print a pipeline result."""
    print(f"  [{result.get('session_id', '?')}] {result.get('result', '?')}")
    if result.get("blocked"):
        print("  Warning: Input was blocked by guard pipeline")


def run_async_main() -> None:
    """Sync wrapper that launches :func:`async_main` via ``asyncio.run``."""
    asyncio.run(async_main())


if __name__ == "__main__":
    if "--async" in sys.argv:
        run_async_main()
    else:
        main()
