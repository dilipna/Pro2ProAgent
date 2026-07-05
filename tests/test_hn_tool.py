from p2pops.tools.hn import search_hn


def test_search_hn_returns_stories():
    stories = search_hn("LangGraph", limit=3)

    assert 0 < len(stories) <= 3
    assert all(story.hn_url.startswith("https://news.ycombinator.com/item?id=") for story in stories)
    assert all(story.points >= 0 for story in stories)
