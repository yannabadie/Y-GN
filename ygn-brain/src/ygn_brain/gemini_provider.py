"""Gemini CLI provider — runs ``gemini`` as a subprocess for LLM inference."""

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

_DEFAULT_MODEL = "gemini-3.1-pro-preview"
_DEFAULT_TIMEOUT = 300


class GeminiCliError(Exception):
    """Raised when the Gemini CLI returns an error."""

    def __init__(self, message: str, returncode: int | None = None) -> None:
        self.returncode = returncode
        super().__init__(message)


class GeminiCliProvider(LLMProvider):
    """LLM provider that delegates to the ``gemini`` CLI.

    Uses the user's existing Gemini CLI authentication (Google login),
    so no API key or SDK charges are incurred.

    Configuration via environment variables:
        - ``YGN_GEMINI_MODEL``: model name (default ``gemini-3.1-pro-preview``)
        - ``YGN_LLM_TIMEOUT_SEC``: subprocess timeout in seconds (default 300)
    """

    def __init__(
        self,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._model = model or os.environ.get("YGN_GEMINI_MODEL", _DEFAULT_MODEL)
        self._timeout = timeout or float(
            os.environ.get("YGN_LLM_TIMEOUT_SEC", str(_DEFAULT_TIMEOUT))
        )

    def name(self) -> str:
        return "gemini"

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
        """Send a chat request via ``gemini`` CLI."""
        prompt = self._build_prompt(request)
        model = request.model or self._model

        # Check that gemini is available
        gemini_bin = shutil.which("gemini")
        if gemini_bin is None:
            msg = (
                "gemini CLI not found on PATH. "
                "Install it or set YGN_LLM_PROVIDER=stub to use the stub provider."
            )
            raise GeminiCliError(msg)

        # Run gemini CLI with JSON output
        args = [
            gemini_bin,
            "--prompt",
            prompt,
            "--output-format",
            "json",
            "-m",
            model,
        ]
        try:
            proc = await self._spawn(args)
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )
        except TimeoutError as exc:
            msg = f"gemini CLI timed out after {self._timeout}s"
            raise GeminiCliError(msg) from exc

        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr = stderr_bytes.decode("utf-8", errors="replace").strip()

        if proc.returncode != 0:
            detail = stderr or stdout or "unknown error"
            # Detect common auth errors
            if "auth" in detail.lower() or "login" in detail.lower():
                msg = (
                    f"gemini CLI auth error (exit {proc.returncode}): {detail}. "
                    "Run 'gemini auth login' to authenticate."
                )
            else:
                msg = f"gemini CLI failed (exit {proc.returncode}): {detail}"
            raise GeminiCliError(msg, returncode=proc.returncode)

        # Parse JSON response; extract .response if present, else fallback to raw text
        content = self._parse_response(stdout)

        prompt_tokens = len(prompt.split())
        completion_tokens = len(content.split())

        return ChatResponse(
            content=content,
            tool_calls=[],
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            ),
        )

    async def chat_with_tools(self, request: ChatRequest, tools: list[ToolSpec]) -> ChatResponse:
        """MVP: include tool descriptions in the prompt text, then call chat()."""
        if not tools:
            return await self.chat(request)

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
        """Spawn a subprocess, handling Windows .CMD/.BAT scripts."""
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
    def _parse_response(stdout: str) -> str:
        """Extract the response text from Gemini CLI JSON output.

        Expected format: ``{"response": "..."}`` or similar JSON structure.
        Falls back to raw stdout if JSON parsing fails.
        """
        if not stdout:
            return ""
        try:
            data = json.loads(stdout)
            if isinstance(data, dict):
                # Try common response field names
                for key in ("response", "text", "content", "output"):
                    if key in data:
                        val = data[key]
                        return str(val) if not isinstance(val, str) else val
                # If no known key, stringify the whole object
                return json.dumps(data)
            return str(data)
        except (json.JSONDecodeError, ValueError):
            # Not JSON — return raw text
            return stdout
