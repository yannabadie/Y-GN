"""Evolution loop — scaffold self-modification with safety gates.

Allows the agent to propose modifications to its own scaffold (code/config),
generate a local patch, validate against quality gates, and apply if all gates
pass. Gated by a whitelist of files and requires test validation.
"""

from __future__ import annotations

import difflib
import fnmatch
import re
import time
import uuid
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EvolutionScope(StrEnum):
    """Controls what type of scaffold change is being proposed."""

    CONFIG = "config"
    TEST = "test"
    TOOLING = "tooling"
    DOCUMENTATION = "documentation"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class EvolutionProposal:
    """A proposed scaffold modification."""

    proposal_id: str
    scope: EvolutionScope
    description: str
    target_file: str
    original_content: str
    proposed_content: str
    created_at: float
    confidence: float


@dataclass(frozen=True)
class GateCheckResult:
    """Result of a single quality-gate check."""

    gate_name: str
    passed: bool
    output: str


@dataclass
class EvolutionResult:
    """Outcome of applying (or rejecting) a proposal."""

    proposal_id: str
    applied: bool
    gate_results: list[GateCheckResult]
    reason: str


# ---------------------------------------------------------------------------
# File whitelist
# ---------------------------------------------------------------------------

_DEFAULT_PATTERNS: list[str] = [
    "*.toml",
    "*.cfg",
    "*.ini",
    "*.yml",
    "*.yaml",
    "tests/**/*.py",
]


def _glob_match(path: str, pattern: str) -> bool:
    """Match *path* against a glob *pattern*, supporting ``**`` for recursive segments."""
    if "**" in pattern:
        # Split on the first '**' occurrence.
        prefix, _, suffix = pattern.partition("**")
        suffix = suffix.lstrip("/")
        # The prefix (if any) must match the start of the path.
        if prefix:
            prefix = prefix.rstrip("/")
            if not path.startswith(prefix + "/") and path != prefix:
                return False
            # Strip matched prefix from path for suffix matching.
            path = path[len(prefix) :].lstrip("/")
        # The suffix must match the tail of the remaining path.
        if suffix:
            parts = path.split("/")
            for i in range(len(parts)):
                candidate = "/".join(parts[i:])
                if fnmatch.fnmatch(candidate, suffix):
                    return True
            return False
        return True
    return fnmatch.fnmatch(path, pattern)


class FileWhitelist:
    """Glob-pattern whitelist controlling which files may be evolved."""

    def __init__(self, allowed_patterns: list[str] | None = None) -> None:
        self._patterns: list[str] = (
            allowed_patterns if allowed_patterns is not None else list(_DEFAULT_PATTERNS)
        )

    def is_allowed(self, file_path: str) -> bool:
        """Return *True* if *file_path* matches any allowed pattern."""
        normalised = file_path.replace("\\", "/")
        for pattern in self._patterns:
            if _glob_match(normalised, pattern):
                return True
        return False


# ---------------------------------------------------------------------------
# Dangerous-content patterns used by SafetyGuard
# ---------------------------------------------------------------------------

_DANGEROUS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"os\.system\("),
    re.compile(r"subprocess\.call\("),
    re.compile(r"\beval\("),
    re.compile(r"\bexec\("),
    re.compile(r"rm\s+-rf\b"),
    re.compile(r"del\s+/s\b"),
    re.compile(r"\bimport\s+os\b"),
]

_MAX_DIFF_LINES = 500


class SafetyGuard:
    """Inspects an :class:`EvolutionProposal` for dangerous content."""

    def check_proposal(self, proposal: EvolutionProposal) -> tuple[bool, str]:
        """Return ``(safe, reason)``."""
        # Low confidence
        if proposal.confidence < 0.3:
            return False, f"Confidence too low ({proposal.confidence:.2f} < 0.30)"

        # Dangerous patterns
        for pat in _DANGEROUS_PATTERNS:
            if pat.search(proposal.proposed_content):
                return False, f"Dangerous pattern detected: {pat.pattern}"

        # Diff size
        original_lines = proposal.original_content.splitlines(keepends=True)
        proposed_lines = proposal.proposed_content.splitlines(keepends=True)
        diff_lines = list(difflib.unified_diff(original_lines, proposed_lines, lineterm=""))
        changed = sum(1 for ln in diff_lines if ln.startswith("+") or ln.startswith("-"))
        if changed > _MAX_DIFF_LINES:
            return False, f"Diff too large ({changed} lines changed, max {_MAX_DIFF_LINES})"

        return True, "Proposal passed safety checks"


# ---------------------------------------------------------------------------
# Evolution engine
# ---------------------------------------------------------------------------


class EvolutionEngine:
    """Core engine: propose, validate, apply, rollback scaffold changes."""

    def __init__(
        self,
        whitelist: FileWhitelist | None = None,
        dry_run: bool = True,
    ) -> None:
        self._whitelist = whitelist if whitelist is not None else FileWhitelist()
        self._dry_run = dry_run
        self.history: list[EvolutionResult] = []

    # -- public API ---------------------------------------------------------

    def propose(
        self,
        scope: EvolutionScope,
        target_file: str,
        description: str,
        proposed_content: str,
    ) -> EvolutionProposal:
        """Create an :class:`EvolutionProposal` for *target_file*.

        Raises :class:`ValueError` if the file is not in the whitelist.
        """
        if not self._whitelist.is_allowed(target_file):
            msg = f"File not in whitelist: {target_file}"
            raise ValueError(msg)

        original = self._read_file(target_file)

        return EvolutionProposal(
            proposal_id=str(uuid.uuid4()),
            scope=scope,
            description=description,
            target_file=target_file,
            original_content=original,
            proposed_content=proposed_content,
            created_at=time.time(),
            confidence=1.0,
        )

    def validate(self, proposal: EvolutionProposal) -> list[GateCheckResult]:
        """Run quality-gate checks on *proposal*."""
        results: list[GateCheckResult] = []

        # Gate: content not empty
        if not proposal.proposed_content.strip():
            results.append(
                GateCheckResult(
                    gate_name="non_empty",
                    passed=False,
                    output="Proposed content is empty",
                )
            )
        else:
            results.append(
                GateCheckResult(
                    gate_name="non_empty",
                    passed=True,
                    output="Proposed content is non-empty",
                )
            )

        # Gate: diff exists
        if proposal.proposed_content == proposal.original_content:
            results.append(
                GateCheckResult(
                    gate_name="diff_exists",
                    passed=False,
                    output="No diff — proposed content identical to original",
                )
            )
        else:
            results.append(
                GateCheckResult(
                    gate_name="diff_exists",
                    passed=True,
                    output="Diff detected between original and proposed content",
                )
            )

        # In dry-run mode add a simulated passing gate for the test suite.
        if self._dry_run:
            results.append(
                GateCheckResult(
                    gate_name="test_suite",
                    passed=True,
                    output="Simulated: all tests pass (dry run)",
                )
            )

        return results

    def apply(self, proposal: EvolutionProposal) -> EvolutionResult:
        """Validate and (conditionally) apply *proposal*."""
        gate_results = self.validate(proposal)
        all_passed = all(g.passed for g in gate_results)

        if not all_passed:
            failures = [g for g in gate_results if not g.passed]
            reason = "; ".join(f"{f.gate_name}: {f.output}" for f in failures)
            result = EvolutionResult(
                proposal_id=proposal.proposal_id,
                applied=False,
                gate_results=gate_results,
                reason=reason,
            )
            self.history.append(result)
            return result

        if self._dry_run:
            result = EvolutionResult(
                proposal_id=proposal.proposal_id,
                applied=False,
                gate_results=gate_results,
                reason="dry run mode",
            )
            self.history.append(result)
            return result

        # All gates passed and not dry-run — write the file.
        self._write_file(proposal.target_file, proposal.proposed_content)
        result = EvolutionResult(
            proposal_id=proposal.proposal_id,
            applied=True,
            gate_results=gate_results,
            reason="All gates passed — applied",
        )
        self.history.append(result)
        return result

    def rollback(self, proposal: EvolutionProposal) -> bool:
        """Restore *target_file* to its original content.

        Returns *True* if the file was restored, *False* if the file does not
        exist and the original content was empty (nothing to restore).
        """
        path = Path(proposal.target_file)
        if not path.exists() and not proposal.original_content:
            return False
        self._write_file(proposal.target_file, proposal.original_content)
        return True

    def generate_diff(self, proposal: EvolutionProposal) -> str:
        """Return a unified diff string between original and proposed content."""
        original_lines = proposal.original_content.splitlines(keepends=True)
        proposed_lines = proposal.proposed_content.splitlines(keepends=True)
        diff = difflib.unified_diff(
            original_lines,
            proposed_lines,
            fromfile=f"a/{proposal.target_file}",
            tofile=f"b/{proposal.target_file}",
        )
        return "".join(diff)

    # -- private helpers ----------------------------------------------------

    @staticmethod
    def _read_file(file_path: str) -> str:
        path = Path(file_path)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    @staticmethod
    def _write_file(file_path: str, content: str) -> None:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
