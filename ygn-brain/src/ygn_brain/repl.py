"""Simple REPL for ygn-brain — interactive orchestrator loop."""

from __future__ import annotations

from pathlib import Path

from .orchestrator import Orchestrator


def main() -> None:
    print("ygn-brain REPL v0.1.0 — type 'quit' to exit")
    orch = Orchestrator()
    evidence_dir = Path("./evidence")
    evidence_dir.mkdir(exist_ok=True)

    while True:
        try:
            user_input = input("brain> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if user_input.lower() in ("quit", "exit"):
            break
        if not user_input:
            continue

        result = orch.run(user_input)
        print(f"  => {result['result']}")

        # Save evidence pack
        path = orch.evidence.save(evidence_dir)
        print(f"  [evidence saved: {path}]")

        # Reset for next turn
        orch = Orchestrator()


if __name__ == "__main__":
    main()
