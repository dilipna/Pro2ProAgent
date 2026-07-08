"""Product publishing: turn a complete build's files into a real, live URL.

This is the Publish stage of the loop. Deterministic code (same line as
venture/build scoring): the LLM agents produce the product's files upstream;
this module only packages them (ensure an entry page, inject attribution)
and pushes them to Vercel's deployment API, then smoke-checks the result
before anyone calls it "Live".

Degrades honestly: with no VERCEL_TOKEN configured, the build-squad publish
node skips this module entirely and the build stays "complete, unpublished"
rather than pretending. A failed deploy or smoke check is an error event,
never a silent success.
"""

import asyncio
import logging
import re

import httpx

from .build.schemas import ScaffoldFile
from .config import get_settings

logger = logging.getLogger(__name__)

VERCEL_API = "https://api.vercel.com"
DEPLOY_POLL_SECONDS = 4.0
DEPLOY_TIMEOUT_SECONDS = 240.0

# Only browser-servable files ship; anything else the squad produced (SQL
# sketches, backend scaffolds) stays in the dossier as documentation.
_DEPLOYABLE_SUFFIXES = (".html", ".css", ".js", ".json", ".svg", ".txt", ".md")


class PublishError(RuntimeError):
    """Raised when packaging/deploy/smoke-check cannot produce a live URL."""


def product_slug(ptp_number: int, product_name: str) -> str:
    """Deterministic Vercel project name: `ptp-004-productname`. Lowercase
    alphanumeric + dashes, bounded well inside Vercel's project-name limit."""
    base = re.sub(r"[^a-z0-9]+", "-", product_name.lower()).strip("-") or "product"
    return f"ptp-{ptp_number:03d}-{base}"[:48].rstrip("-")


def _attribution(ptp_number: int, product_name: str) -> str:
    """A small fixed badge linking the product back to its ProToPro story.
    Injected before </body> so every shipped product self-identifies."""
    return (
        '\n<div style="position:fixed;right:12px;bottom:12px;z-index:9999;'
        "background:#0b090a;color:#948a8e;border:1px solid #2a242a;border-radius:99px;"
        'padding:6px 12px;font:11px ui-monospace,monospace;opacity:.85">'
        f'<a href="https://protopro.vercel.app/showcase/ptp-{ptp_number:03d}" '
        'style="color:#c9bec2;text-decoration:none" rel="noopener">'
        f"PTP-{ptp_number:03d} · built autonomously by ProToPro</a></div>\n"
    )


def package_product(files: list[ScaffoldFile], ptp_number: int, product_name: str) -> dict[str, str]:
    """Compose the deployable file set. Guarantees an index.html (promoting
    the first HTML file if the squad named it differently) and injects the
    attribution badge into every HTML page."""
    bundle: dict[str, str] = {}
    for f in files:
        path = f.path.lstrip("/")
        if path.lower().endswith(_DEPLOYABLE_SUFFIXES):
            bundle[path] = f.content

    html_paths = [p for p in bundle if p.lower().endswith(".html")]
    if not html_paths:
        raise PublishError(
            "no HTML entry page in the build output — nothing browser-servable to publish"
        )
    if "index.html" not in bundle:
        bundle["index.html"] = bundle.pop(html_paths[0])

    badge = _attribution(ptp_number, product_name)
    for path in [p for p in bundle if p.lower().endswith(".html")]:
        content = bundle[path]
        if "</body>" in content:
            bundle[path] = content.replace("</body>", f"{badge}</body>", 1)
        else:
            bundle[path] = content + badge
    return bundle


async def _team_id(client: httpx.AsyncClient, headers: dict) -> str | None:
    settings = get_settings()
    if settings.vercel_team_id:
        return settings.vercel_team_id
    response = await client.get(f"{VERCEL_API}/v2/user", headers=headers)
    response.raise_for_status()
    return response.json().get("user", {}).get("defaultTeamId")


async def deploy_product(slug: str, bundle: dict[str, str]) -> str:
    """Create a Vercel production deployment from inline files and wait for
    it to reach READY. Returns the deployment's public URL."""
    settings = get_settings()
    if not settings.vercel_token:
        raise PublishError("VERCEL_TOKEN is not configured")
    headers = {"Authorization": f"Bearer {settings.vercel_token}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        team_id = await _team_id(client, headers)
        params = {"teamId": team_id} if team_id else {}
        response = await client.post(
            f"{VERCEL_API}/v13/deployments",
            headers=headers,
            params=params,
            json={
                "name": slug,
                "target": "production",
                "files": [{"file": path, "data": data} for path, data in sorted(bundle.items())],
                "projectSettings": {"framework": None},
            },
        )
        if response.status_code >= 400:
            raise PublishError(f"Vercel deployment rejected ({response.status_code}): {response.text[:300]}")
        deployment = response.json()
        deployment_id = deployment["id"]

        elapsed = 0.0
        while True:
            status = await client.get(
                f"{VERCEL_API}/v13/deployments/{deployment_id}", headers=headers, params=params
            )
            status.raise_for_status()
            data = status.json()
            state = data.get("readyState") or data.get("status")
            if state == "READY":
                # Prefer the stable project alias over the per-deployment URL.
                aliases = data.get("alias") or []
                host = min(aliases, key=len) if aliases else data.get("url")
                if not host:
                    raise PublishError("deployment READY but no URL returned")
                return f"https://{host}"
            if state in ("ERROR", "CANCELED"):
                raise PublishError(f"deployment ended in state {state}")
            if elapsed >= DEPLOY_TIMEOUT_SECONDS:
                raise PublishError(f"deployment not READY after {DEPLOY_TIMEOUT_SECONDS:.0f}s")
            await asyncio.sleep(DEPLOY_POLL_SECONDS)
            elapsed += DEPLOY_POLL_SECONDS


async def smoke_check(url: str) -> None:
    """Minimal post-deploy QA: the URL must answer 200 with a non-trivial
    HTML document before the showcase is allowed to say 'Live'."""
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        response = await client.get(url)
    if response.status_code != 200:
        raise PublishError(f"smoke check failed: {url} answered {response.status_code}")
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type:
        raise PublishError(f"smoke check failed: {url} served {content_type!r}, not HTML")
    if len(response.text) < 200:
        raise PublishError(f"smoke check failed: {url} body suspiciously small ({len(response.text)} chars)")


async def publish_product(files: list[ScaffoldFile], ptp_number: int, product_name: str) -> str:
    """Package → deploy → smoke check. The one entrypoint the build graph calls."""
    bundle = package_product(files, ptp_number, product_name)
    slug = product_slug(ptp_number, product_name)
    url = await deploy_product(slug, bundle)
    await smoke_check(url)
    return url
