"""Interactive REPL for the Y-GN Brain pipeline."""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

from .orchestrator import Orchestrator
from .provider import LLMProvider, StubLLMProvider


def main() -> None:
    """Entry point for ``ygn-brain-repl`` command (synchronous)."""
    print("Y-GN Brain REPL v0.1.0")
    print("Type 'quit' or 'exit' to exit, 'status' for pipeline info")
    print("Using StubLLMProvider (set ANTHROPIC_API_KEY for Claude)")
    print()

    provider: LLMProvider = StubLLMProvider()
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
            print("Anything else is processed as a task through the pipeline")
            continue

        # Run through orchestrator
        result = orchestrator.run(stripped)
        _print_result(result)


async def async_main() -> None:
    """Async entry point using real LLM providers when available."""
    provider: LLMProvider
    print("Y-GN Brain REPL v0.1.0 (async)")
    if os.environ.get("ANTHROPIC_API_KEY"):
        # TODO: wire real Claude provider when available
        print("Note: ANTHROPIC_API_KEY detected but real providers not yet shipped.")
        print("Using StubLLMProvider (deterministic responses)")
        provider = StubLLMProvider()
    elif os.environ.get("OPENAI_API_KEY"):
        # TODO: wire real OpenAI provider when available
        print("Note: OPENAI_API_KEY detected but real providers not yet shipped.")
        print("Using StubLLMProvider (deterministic responses)")
        provider = StubLLMProvider()
    else:
        print("Using StubLLMProvider (set ANTHROPIC_API_KEY for Claude)")
        provider = StubLLMProvider()

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
