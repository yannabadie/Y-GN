"""Guard model download and management.

CLI: ygn-brain-guard-download
Downloads PromptGuard-86M from HuggingFace, exports to ONNX.
"""

from __future__ import annotations

import os
from pathlib import Path


def get_model_dir() -> str:
    """Return the model directory path."""
    env = os.environ.get("YGN_GUARD_MODEL_DIR")
    if env:
        return env
    return str(Path.home() / ".ygn" / "models")


def ensure_model_dir(path: str) -> None:
    """Create model directory if it doesn't exist."""
    os.makedirs(path, exist_ok=True)


def download_prompt_guard(model_dir: str | None = None) -> str:
    """Download PromptGuard-86M and export to ONNX.

    Returns the path to the model directory.
    Requires: pip install 'ygn-brain[ml]'
    """
    target = model_dir or os.path.join(get_model_dir(), "prompt-guard-86m")
    ensure_model_dir(target)

    try:
        from optimum.onnxruntime import ORTModelForSequenceClassification
        from transformers import AutoTokenizer
    except ImportError as e:
        raise ImportError(
            "optimum and transformers required. "
            "Install with: pip install 'ygn-brain[ml]'"
        ) from e

    print(f"Downloading PromptGuard-86M to {target}...")  # noqa: T201
    model = ORTModelForSequenceClassification.from_pretrained(
        "meta-llama/Prompt-Guard-86M",
        export=True,
    )
    tokenizer = AutoTokenizer.from_pretrained("meta-llama/Prompt-Guard-86M")

    model.save_pretrained(target)
    tokenizer.save_pretrained(target)
    print(f"Model saved to {target}")  # noqa: T201
    return target


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Download guard ML model")
    parser.add_argument(
        "--model-dir",
        default=None,
        help="Target directory (default: ~/.ygn/models/prompt-guard-86m)",
    )
    args = parser.parse_args()
    download_prompt_guard(args.model_dir)


if __name__ == "__main__":
    main()
