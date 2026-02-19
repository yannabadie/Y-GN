"""Tests for context compression — strategies, token estimation, edge cases."""

from ygn_brain.context_compression import (
    CompressionStrategy,
    ContextCompressor,
)


def test_truncate_strategy():
    """Truncate keeps first N items that fit."""
    compressor = ContextCompressor(max_tokens=8, strategy=CompressionStrategy.TRUNCATE)
    items = [
        "short sentence here",
        "another short one",
        "this will be dropped because it goes over the token budget",
    ]
    result = compressor.compress(items)
    assert result.strategy_used == CompressionStrategy.TRUNCATE
    assert result.dropped_count > 0
    assert result.compressed_length <= 8


def test_sliding_window_strategy():
    """Sliding window keeps last (most recent) items that fit."""
    compressor = ContextCompressor(max_tokens=20, strategy=CompressionStrategy.SLIDING_WINDOW)
    items = [
        "oldest item that should be dropped",
        "middle item here",
        "newest item kept",
    ]
    result = compressor.compress(items)
    assert result.strategy_used == CompressionStrategy.SLIDING_WINDOW
    # The newest item should be in the content
    assert "newest item kept" in result.content
    assert result.compressed_length <= 20


def test_priority_strategy():
    """Priority keeps highest-priority items first."""
    compressor = ContextCompressor(max_tokens=20, strategy=CompressionStrategy.PRIORITY)
    items = [
        "low priority item",
        "high priority item",
        "medium priority item",
    ]
    priorities = [0.1, 0.9, 0.5]
    result = compressor.compress(items, priorities=priorities)
    assert result.strategy_used == CompressionStrategy.PRIORITY
    # High priority item should be present
    assert "high priority item" in result.content
    assert result.compressed_length <= 20


def test_summarize_strategy():
    """Summarize concatenates with separator and truncates."""
    compressor = ContextCompressor(max_tokens=50, strategy=CompressionStrategy.SUMMARIZE)
    items = ["first item", "second item", "third item"]
    result = compressor.compress(items)
    assert result.strategy_used == CompressionStrategy.SUMMARIZE
    assert " | " in result.content
    assert result.compressed_length <= 50


def test_estimate_tokens():
    """Token estimation approximates based on word count."""
    compressor = ContextCompressor()
    # 3 words / 0.75 = 4
    assert compressor.estimate_tokens("one two three") == 4
    assert compressor.estimate_tokens("") == 0


def test_fits():
    """fits() returns True when text is within budget."""
    compressor = ContextCompressor(max_tokens=10)
    assert compressor.fits("short") is True
    # Very long text should not fit in 10 tokens
    long_text = " ".join(["word"] * 100)
    assert compressor.fits(long_text) is False


def test_empty_input():
    """Compressing an empty list returns an empty result."""
    compressor = ContextCompressor()
    result = compressor.compress([])
    assert result.original_length == 0
    assert result.compressed_length == 0
    assert result.content == ""
    assert result.dropped_count == 0


def test_all_items_fit():
    """When all items fit, nothing is dropped."""
    compressor = ContextCompressor(max_tokens=1000, strategy=CompressionStrategy.TRUNCATE)
    items = ["hello world", "goodbye world"]
    result = compressor.compress(items)
    assert result.dropped_count == 0
    assert "hello world" in result.content
    assert "goodbye world" in result.content
