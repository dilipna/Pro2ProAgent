"""The review email is best-effort: a delivery failure must not crash the
run, because the review tokens already exist and the operator can still
approve from the console queue."""

from types import SimpleNamespace

from p2pops import notify


def _fixtures():
    run = SimpleNamespace(id="run1234abcd", topic="agent observability")
    idea = SimpleNamespace(
        id="idea1", title="A problem", description="desc", reasoning="why", score=72
    )
    review = SimpleNamespace(id="tok_abc")
    return run, [idea], {idea.id: review}


async def test_send_review_request_swallows_delivery_failure(monkeypatch):
    class Boom:
        async def send(self, **_):
            raise RuntimeError("403 Forbidden for url 'https://api.resend.com/emails'")

    monkeypatch.setattr(notify, "get_notifier", lambda: Boom())
    monkeypatch.setattr(notify, "get_settings", lambda: SimpleNamespace(
        review_email_to="me@example.com", review_token_ttl_hours=72, app_base_url="http://x"
    ))

    run, ideas, reviews = _fixtures()
    # Must return False rather than raise — the run proceeds to the gate.
    assert await notify.send_review_request(run, ideas, reviews) is False


async def test_send_review_request_reports_success(monkeypatch):
    sent = {}

    class Ok:
        async def send(self, **kwargs):
            sent.update(kwargs)

    monkeypatch.setattr(notify, "get_notifier", lambda: Ok())
    monkeypatch.setattr(notify, "get_settings", lambda: SimpleNamespace(
        review_email_to="me@example.com", review_token_ttl_hours=72, app_base_url="http://x"
    ))

    run, ideas, reviews = _fixtures()
    assert await notify.send_review_request(run, ideas, reviews) is True
    assert sent["to"] == "me@example.com"
