"""Tests for guard model download."""

import os
import tempfile

from ygn_brain.guard_download import ensure_model_dir, get_model_dir


def test_get_model_dir_default():
    d = get_model_dir()
    assert d.endswith("models")


def test_get_model_dir_from_env(monkeypatch, tmp_path):
    target = str(tmp_path / "ygn-test-models")
    monkeypatch.setenv("YGN_GUARD_MODEL_DIR", target)
    d = get_model_dir()
    assert d == target


def test_ensure_model_dir_creates():
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "subdir", "models")
        ensure_model_dir(path)
        assert os.path.isdir(path)
