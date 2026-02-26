"""Tests for ML-based guard classifiers."""

from ygn_brain.guard import GuardBackend
from ygn_brain.guard_backends import ClassifierGuard


def test_onnx_classifier_is_guard_backend():
    from ygn_brain.guard_ml import OnnxClassifierGuard

    assert issubclass(OnnxClassifierGuard, ClassifierGuard)
    assert issubclass(OnnxClassifierGuard, GuardBackend)


def test_onnx_classifier_stub_mode():
    """In stub mode (no real model), classify returns safe."""
    from ygn_brain.guard_ml import OnnxClassifierGuard

    guard = OnnxClassifierGuard(model_path=None, stub=True)
    is_safe, score = guard.classify("hello world")
    assert is_safe is True
    assert score == 0.0


def test_onnx_classifier_check_returns_guard_result():
    from ygn_brain.guard_ml import OnnxClassifierGuard

    guard = OnnxClassifierGuard(model_path=None, stub=True)
    result = guard.check("hello world")
    assert result.allowed is True
    assert result.score == 0.0


def test_onnx_classifier_name():
    from ygn_brain.guard_ml import OnnxClassifierGuard

    guard = OnnxClassifierGuard(model_path=None, stub=True)
    assert guard.name() == "OnnxClassifierGuard"
