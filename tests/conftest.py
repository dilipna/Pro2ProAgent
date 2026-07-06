import pytest

from p2pops.config import get_settings
from p2pops.db.engine import dispose_engine, init_db
from p2pops.models import AnalyzedIdea


def make_idea(status: str = "shortlisted", title: str = "Test problem") -> AnalyzedIdea:
    return AnalyzedIdea(
        title=title,
        description="A test description",
        source_url="https://example.com",
        score=80,
        reasoning="Looks promising",
        status=status,
    )


@pytest.fixture
async def db(tmp_path, monkeypatch):
    """Isolated database in a temp data dir for each test."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    await dispose_engine()
    await init_db()
    yield
    await dispose_engine()
    get_settings.cache_clear()
