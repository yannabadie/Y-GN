"""Codex CLI provider — runs ``codex`` as a subprocess for LLM inference."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys

from .provider import (
    ChatRequest,
    ChatResponse,
    LLMProvider,
    ProviderCapabilities,
    TokenUsage,
    ToolSpec,
)

_DEFAULT_MODEL = "gpt-5.2-codex"
_DEFAULT_TIMEOUT = 300


class CodexCliError(Exception):
    """Raised when the Codex CLI returns an error."""

    def __init__(self, message: str, returncode: int | None = None) -> None:
        self.returncode = returncode
        super().__init__(message)


class CodexCliProvider(LLMProvider):
    """LLM provider that delegates to the ``codex`` CLI.

    Uses the user's existing Codex CLI authentication (subscription-based),
    so no API key or SDK charges are incurred.

    Configuration via environment variables:
        - ``YGN_CODEX_MODEL``: model name (default ``gpt-5.2-codex``)
        - ``YGN_LLM_TIMEOUT_SEC``: subprocess timeout in seconds (default 300)
    """

    def __init__(
        self,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._model = model or os.environ.get("YGN_CODEX_MODEL", _DEFAULT_MODEL)
        self._timeout = timeout or float(
            os.environ.get("YGN_LLM_TIMEOUT_SEC", str(_DEFAULT_TIMEOUT))
        )

    def name(self) -> str:
        return "codex"

    def is_available(self) -> bool:
        """Check if the codex CLI is installed and accessible on PATH.

        On Windows, npm-installed CLIs are ``.cmd`` batch scripts, so we
        also look for ``codex.cmd``.
        """
        return (
            shutil.which("codex") is not None
            or shutil.which("codex.cmd") is not None
        )

    @property
    def model(self) -> str:
        """Return the configured model name."""
        return self._model

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            native_tool_calling=False,
            vision=False,
            streaming=False,
        )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a chat request via ``codex exec --json --full-auto``."""
        # Build the prompt from messages
        prompt = self._build_prompt(request)
        model = request.model or self._model

        # Check that codex is available (also handles codex.cmd on Windows)
        codex_bin = shutil.which("codex") or shutil.which("codex.cmd")
        if codex_bin is None:
            msg = (
                "codex CLI not found on PATH. "
                "Install it or set YGN_LLM_PROVIDER=stub to use the stub provider."
            )
            raise CodexCliError(msg)

        # Run codex exec with --json (structured JSONL) and --full-auto
        # (auto-approve in sandbox to prevent hanging on approval prompts)
        args = [codex_bin, "exec", prompt, "-m", model, "--json", "--full-auto"]
        try:
            proc = await self._spawn(args)
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )
        except TimeoutError as exc:
            msg = f"codex exec timed out after {self._timeout}s"
            raise CodexCliError(msg) from exc

        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr = stderr_bytes.decode("utf-8", errors="replace").strip()

        if proc.returncode != 0:
            detail = stderr or stdout or "unknown error"
            msg = f"codex exec failed (exit {proc.returncode}): {detail}"
            raise CodexCliError(msg, returncode=proc.returncode)

        # Parse JSONL output to extract the agent_message and token usage
        content, usage = self._parse_jsonl_response(stdout)

        return ChatResponse(
            content=content,
            tool_calls=[],
            usage=usage,
        )

    async def chat_with_tools(self, request: ChatRequest, tools: list[ToolSpec]) -> ChatResponse:
        """MVP: include tool descriptions in the prompt text, then call chat()."""
        if not tools:
            return await self.chat(request)

        # Inject tool descriptions as a system-level instruction
        tool_text = "\n".join(
            f"- {t.name}: {t.description} (params: {t.parameters})" for t in tools
        )
        augmented = request.model_copy()
        last_msg = augmented.messages[-1] if augmented.messages else None
        if last_msg is not None:
            last_msg.content = (
                f"Available tools:\n{tool_text}\n\n"
                f"If you need a tool, respond with JSON: "
                f'{{"tool": "<name>", "arguments": {{...}}}}\n\n'
                f"{last_msg.content}"
            )
        return await self.chat(augmented)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _spawn(
        args: list[str],
    ) -> asyncio.subprocess.Process:
        """Spawn a subprocess, handling Windows .CMD/.BAT scripts.

        On Windows, npm-installed CLIs are ``.CMD`` batch scripts that
        ``CreateProcess`` cannot execute directly.  We use
        ``create_subprocess_shell`` with ``subprocess.list2cmdline``
        to go through ``cmd.exe`` in that case.
        """
        if sys.platform == "win32" and args[0].lower().endswith((".cmd", ".bat")):
            cmd_line = subprocess.list2cmdline(args)
            return await asyncio.create_subprocess_shell(
                cmd_line,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        return await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    @staticmethod
    def _build_prompt(request: ChatRequest) -> str:
        """Flatten ChatRequest messages into a single prompt string."""
        parts: list[str] = []
        for msg in request.messages:
            if msg.role == "system":
                parts.append(f"[System] {msg.content}")
            elif msg.role == "user":
                parts.append(msg.content)
            elif msg.role == "assistant":
                parts.append(f"[Assistant] {msg.content}")
            else:
                parts.append(f"[{msg.role}] {msg.content}")
        return "\n\n".join(parts)

    @staticmethod
    def _parse_jsonl_response(stdout: str) -> tuple[str, TokenUsage]:
        """Parse codex ``--json`` JSONL output.

        Extracts the last ``agent_message`` text and token usage from
        ``turn.completed`` events.

        Returns:
            (content, TokenUsage) tuple.
        """
        content_parts: list[str] = []
        prompt_tokens = 0
        completion_tokens = 0

        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue

            event_type = event.get("type", "")

            # Extract agent messages
            if event_type == "item.completed":
                item = event.get("item", {})
                if item.get("type") == "agent_message":
                    text = item.get("text", "")
                    if text:
                        content_parts.append(text)

            # Extract token usage
            elif event_type == "turn.completed":
                usage = event.get("usage", {})
                prompt_tokens += usage.get("input_tokens", 0)
                completion_tokens += usage.get("output_tokens", 0)

        content = "\n".join(content_parts) if content_parts else stdout
        return content, TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
