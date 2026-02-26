"""ML-based guard classifiers.

Provides:
- OnnxClassifierGuard: ONNX Runtime inference (PromptGuard-86M / deberta-v3)
- OllamaClassifierGuard: Ollama chat completion with classification prompt

Install ML deps: pip install 'ygn-brain[ml]'
"""

from __future__ import annotations

from ygn_brain.guard_backends import ClassifierGuard


class OnnxClassifierGuard(ClassifierGuard):
    """Guard using ONNX Runtime for prompt injection classification.

    In stub mode (stub=True), always returns safe. Used for CI testing
    without model downloads.
    """

    def __init__(
        self,
        model_path: str | None = None,
        model_name: str = "prompt-guard-86m",
        stub: bool = False,
    ) -> None:
        self._model_path = model_path
        self._model_name = model_name
        self._stub = stub
        self._session = None
        self._tokenizer = None

    def _load_model(self):
        if self._stub or self._session is not None:
            return
        try:
            import onnxruntime as ort
            from transformers import AutoTokenizer
        except ImportError as e:
            raise ImportError(
                "onnxruntime and transformers required. "
                "Install with: pip install 'ygn-brain[ml]'"
            ) from e

        if self._model_path is None:
            raise ValueError(
                "model_path required for non-stub mode. "
                "Download from HuggingFace: meta-llama/Prompt-Guard-86M"
            )
        self._tokenizer = AutoTokenizer.from_pretrained(self._model_path)
        self._session = ort.InferenceSession(
            f"{self._model_path}/model.onnx"
        )

    def classify(self, text: str) -> tuple[bool, float]:
        if self._stub:
            return (True, 0.0)

        self._load_model()
        inputs = self._tokenizer(
            text, return_tensors="np", truncation=True, max_length=512
        )
        outputs = self._session.run(None, dict(inputs))
        import numpy as np

        probs = np.exp(outputs[0][0]) / np.sum(np.exp(outputs[0][0]))
        injection_prob = float(probs[1]) if len(probs) > 1 else 0.0
        score = injection_prob * 100.0
        is_safe = score < 50.0
        return (is_safe, score)
