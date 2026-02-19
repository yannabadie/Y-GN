# Contributing to Y-GN

## Getting Started

```bash
git clone https://github.com/yannabadie/Y-GN.git
cd Y-GN
make test  # runs all quality gates
```

## Development Workflow

1. Pick a task from ROADMAP.md (respect epic ordering and dependencies).
2. Create a worktree or branch for your epic: `git worktree add ../ygn-<epic> -b epic/<id>`.
3. Write tests first (TDD), then implement.
4. Run quality gates locally before pushing: `make test`.
5. Open a PR. CI must pass.

## Quality Gates

### Rust (ygn-core/)
```bash
cargo fmt --check
cargo clippy -- -D warnings
cargo test
```

### Python (ygn-brain/)
```bash
python -m compileall src/
ruff check .
mypy src/
pytest -q
```

## Commit Messages

Use conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `ci:`, `chore:`.

## Decision Log

Any non-trivial decision must be recorded in `memory-bank/decisionLog.md` with date and rationale.
