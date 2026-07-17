"""Unit tests for durable history persistence."""

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.overnight]


def test_history_add_list_clear(tmp_history):
    tmp_history.add("hello world", score=88, total_time=12.5, target_model="claude")
    items = tmp_history.list()
    assert len(items) == 1
    assert items[0]["score"] == 88
    assert items[0]["model"] == "claude"
    assert "hello" in items[0]["request"]

    tmp_history.clear()
    assert tmp_history.list() == []


def test_history_respects_max(tmp_path):
    from src.core.history_store import HistoryStore

    store = HistoryStore(path=tmp_path / "h.json", max_entries=3)
    for i in range(5):
        store.add(f"req {i}", score=i, total_time=1.0)
    items = store.list()
    assert len(items) == 3
    assert items[0]["request"].startswith("req 4")
