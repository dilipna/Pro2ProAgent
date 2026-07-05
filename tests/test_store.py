from p2pops import store
from p2pops.config import get_settings
from p2pops.models import AnalyzedIdea


def test_save_and_list_ideas(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    get_settings.cache_clear()

    idea = AnalyzedIdea(
        title="Test idea",
        description="A test description",
        source_url="https://example.com",
        score=80,
        reasoning="Looks promising",
        status="shortlisted",
    )
    idea_id = store.save_idea(idea)
    assert idea_id

    rows = store.list_ideas(status="shortlisted")
    assert len(rows) == 1
    assert rows[0]["title"] == "Test idea"
    assert rows[0]["id"] == idea_id

    assert store.list_ideas(status="rejected") == []

    get_settings.cache_clear()
