from p2pops import memory
from p2pops.config import get_settings


def test_find_duplicate_and_remember(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    get_settings.cache_clear()
    memory._get_collection.cache_clear()

    text_a = "LangGraph agents fail silently mid tool-call with no trace context."
    assert memory.find_duplicate(text_a) is None

    memory.remember("idea-1", text_a)

    similar = "Agents built with LangGraph crash quietly during tool calls, no useful trace."
    assert memory.find_duplicate(similar) == "idea-1"

    unrelated = "People want a better recipe app for tracking calories."
    assert memory.find_duplicate(unrelated) is None

    get_settings.cache_clear()
    memory._get_collection.cache_clear()
