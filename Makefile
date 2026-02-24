.PHONY: test test-rust test-python lint lint-rust lint-python fmt security clean

# On Windows (Git Bash / MSYS2) cargo may auto-detect x86_64-pc-windows-gnu
# even when only the MSVC toolchain is installed.  Force the correct target.
ifeq ($(OS),Windows_NT)
  CARGO_TARGET_FLAG ?= --target x86_64-pc-windows-msvc
else
  CARGO_TARGET_FLAG ?=
endif

# Run all quality gates
test: lint test-rust test-python
	@echo "All gates passed."

# Rust gates
test-rust:
	cd ygn-core && cargo test $(CARGO_TARGET_FLAG)

lint-rust:
	cd ygn-core && cargo fmt --check
	cd ygn-core && cargo clippy $(CARGO_TARGET_FLAG) -- -D warnings

fmt-rust:
	cd ygn-core && cargo fmt

# Python gates
test-python:
	cd ygn-brain && pytest -q

lint-python:
	cd ygn-brain && ruff check .
	cd ygn-brain && mypy src/

fmt-python:
	cd ygn-brain && ruff format .

# Combined
lint: lint-rust lint-python

fmt: fmt-rust fmt-python

# Security
security:
	cd ygn-core && cargo deny check $(CARGO_TARGET_FLAG) 2>/dev/null || echo "cargo-deny: configure deny.toml"
	cd ygn-brain && pip-audit || echo "pip-audit: review findings"

# Clean
clean:
	cd ygn-core && cargo clean
	rm -rf ygn-brain/__pycache__ ygn-brain/.mypy_cache ygn-brain/.ruff_cache ygn-brain/.pytest_cache
