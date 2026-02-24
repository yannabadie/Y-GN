"""Codex CLI provider — runs ``codex`` as a subprocess for LLM inference."""

from __future__ import annotations

import asyncio
import os
import shutil

from .provider import (
    ChatRequest,
    ChatResponse,
    LLMProvider,
    ProviderCapabilities,
    TokenUsage,
    ToolSpec,
)

_DEFAULT_MODEL = "gpt-5.3-codex"
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
        - ``YGN_CODEX_MODEL``: model name (default ``gpt-5.3-codex``)
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
        """Send a chat request via ``codex exec``."""
        # Build the prompt from messages
        prompt = self._build_prompt(request)
        model = request.model or self._model

        # Check that codex is available
        codex_bin = shutil.which("codex")
        if codex_bin is None:
            msg = (
                "codex CLI not found on PATH. "
                "Install it or set YGN_LLM_PROVIDER=stub to use the stub provider."
            )
            raise CodexCliError(msg)

        # Run codex exec
        try:
            proc = await asyncio.create_subprocess_exec(
                "codex",
                "exec",
                prompt,
                "-m",
                model,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
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

        # Estimate token usage from prompt/response word counts
        prompt_tokens = len(prompt.split())
        completion_tokens = len(stdout.split())

        return ChatResponse(
            content=stdout,
            tool_calls=[],
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            ),
        )

    async def chat_with_tools(
        self, request: ChatRequest, tools: list[ToolSpec]
    ) -> ChatResponse:
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
