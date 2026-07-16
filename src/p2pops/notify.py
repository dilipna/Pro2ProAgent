"""Email delivery for the human gate (ADR-0002).

`EmailNotifier` is a port with two adapters: Resend (real delivery via
plain HTTP, no SDK dependency) and Console (logs the email so the whole
pipeline runs with zero credentials in development). Selection is
config-driven.
"""

import logging
from typing import Protocol

import httpx
import logfire

from .config import get_settings
from .db.models import Idea, Review, Run

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"


class EmailNotifier(Protocol):
    async def send(self, *, to: str, subject: str, html: str) -> None: ...


class ConsoleEmailNotifier:
    """Development adapter: prints the email instead of sending it."""

    async def send(self, *, to: str, subject: str, html: str) -> None:
        logger.info("=== EMAIL (console adapter) ===")
        logger.info("To: %s", to)
        logger.info("Subject: %s", subject)
        logger.info("%s", html)
        logger.info("=== END EMAIL ===")


class ResendEmailNotifier:
    async def send(self, *, to: str, subject: str, html: str) -> None:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                RESEND_URL,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.resend_from,
                    "to": [to],
                    "subject": subject,
                    "html": html,
                },
            )
            response.raise_for_status()


def get_notifier() -> EmailNotifier:
    settings = get_settings()
    if settings.resend_api_key:
        return ResendEmailNotifier()
    return ConsoleEmailNotifier()


def build_review_email(run: Run, ideas: list[Idea], reviews: dict[str, Review]) -> str:
    """Renders the review request email. `reviews` maps idea_id -> Review."""
    settings = get_settings()
    base = settings.app_base_url.rstrip("/")

    blocks = []
    for idea in ideas:
        review = reviews[idea.id]
        approve = f"{base}/r/{review.id}/approve"
        reject = f"{base}/r/{review.id}/reject"
        blocks.append(
            f"""
            <div style="border:1px solid #2a242a;border-radius:12px;padding:20px;margin:0 0 16px">
              <p style="margin:0;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#c23553">
                Score {idea.score} / 100
              </p>
              <h3 style="margin:8px 0 6px;font-size:17px;color:#f6f1f2">{idea.title}</h3>
              <p style="margin:0 0 6px;font-size:14px;line-height:1.5;color:#c9bec2">{idea.description}</p>
              <p style="margin:0 0 14px;font-size:12px;color:#948a8e">{idea.reasoning or ""}</p>
              <a href="{approve}" style="display:inline-block;background:#a02240;color:#f6f1f2;text-decoration:none;padding:10px 18px;border-radius:99px;font-size:14px;margin-right:8px">Approve build</a>
              <a href="{reject}" style="display:inline-block;color:#948a8e;text-decoration:none;padding:10px 18px;border:1px solid #2a242a;border-radius:99px;font-size:14px">Reject</a>
            </div>"""
        )

    return f"""
    <div style="background:#0b090a;padding:32px;font-family:ui-sans-serif,system-ui,sans-serif">
      <p style="font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#948a8e;margin:0 0 4px">
        ProToPro · human gate
      </p>
      <h2 style="color:#f6f1f2;font-weight:600;margin:0 0 6px">
        {len(ideas)} problem{"s" if len(ideas) != 1 else ""} shortlisted for build approval
      </h2>
      <p style="color:#948a8e;font-size:13px;margin:0 0 24px">
        Run <code>{run.id[:8]}</code> · topic: {run.topic} · links are single-use and expire in {settings.review_token_ttl_hours}h
      </p>
      {"".join(blocks)}
    </div>"""


async def send_review_request(run: Run, ideas: list[Idea], reviews: dict[str, Review]) -> bool:
    """Email the human gate. Best-effort: the review tokens already exist and
    the run is about to pause at the gate, so a delivery failure (an
    unverified Resend sender 403s, say) must NOT crash the run — the operator
    can still approve from the console approval queue. Returns whether the
    email was actually handed off for delivery."""
    settings = get_settings()
    to = settings.review_email_to
    if not to:
        logger.warning("REVIEW_EMAIL_TO not set — review email routed to console adapter")
    notifier = get_notifier() if to else ConsoleEmailNotifier()

    html = build_review_email(run, ideas, reviews)
    subject = f"[ProToPro] {len(ideas)} idea{'s' if len(ideas) != 1 else ''} awaiting your decision"
    try:
        with logfire.span("notify.review_request", run_id=run.id, ideas=len(ideas)):
            await notifier.send(to=to or "console@localhost", subject=subject, html=html)
        return True
    except Exception:
        logger.exception(
            "review email delivery failed — ideas are still awaiting decision in the console queue"
        )
        return False


async def send_product_ready(ptp_number: int | None, product_name: str, deploy_url: str) -> None:
    """The closing email of the loop: the approved idea shipped and is live.
    Same adapter selection as the review email — console-logged until a
    RESEND_API_KEY exists. Best-effort: a notification failure must never
    fail the publish stage that already succeeded."""
    settings = get_settings()
    to = settings.review_email_to
    notifier = get_notifier() if to else ConsoleEmailNotifier()
    ptp = f"PTP-{ptp_number:03d}" if ptp_number is not None else "PTP"
    html = f"""
    <div style="background:#0b090a;padding:32px;font-family:ui-sans-serif,system-ui,sans-serif">
      <p style="font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#948a8e;margin:0 0 4px">
        ProToPro · published
      </p>
      <h2 style="color:#f6f1f2;font-weight:600;margin:0 0 6px">{ptp} · {product_name} is live</h2>
      <p style="color:#948a8e;font-size:13px;margin:0 0 24px">
        The build squad shipped it, QA passed, and the deploy answered a live smoke check.
      </p>
      <a href="{deploy_url}" style="display:inline-block;background:#a02240;color:#f6f1f2;text-decoration:none;padding:10px 18px;border-radius:99px;font-size:14px;margin-right:8px">View the product</a>
      <a href="https://protopro.vercel.app/showcase/{ptp.lower()}" style="display:inline-block;color:#948a8e;text-decoration:none;padding:10px 18px;border:1px solid #2a242a;border-radius:99px;font-size:14px">Read its story</a>
    </div>"""
    try:
        with logfire.span("notify.product_ready", url=deploy_url):
            await notifier.send(
                to=to or "console@localhost",
                subject=f"[ProToPro] {ptp} shipped — {product_name} is live",
                html=html,
            )
    except Exception:
        logger.exception("product-ready notification failed (publish already succeeded)")
