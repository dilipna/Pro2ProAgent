"""Cheap, reproducible source checks for the product-design contract.

These establish a minimum implementation floor, not visual attractiveness,
WCAG conformance, runtime behavior or acceptance. Browser evidence is separate.
Legacy dossiers without a design contract remain readable and are not relabeled.
"""

import re
from html.parser import HTMLParser

from .schemas import ArchitectureSpec, QAIssue, ScaffoldFile
from .scoring import scaffold_target, undefined_dom_ids


class _Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags: list[tuple[str, dict]] = []
        self.controls: list[tuple[str, dict, bool]] = []
        self.label_depth = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.tags.append((tag, attributes))
        if tag == "label":
            self.label_depth += 1
        if tag in {"input", "select", "textarea"}:
            self.controls.append((tag, attributes, self.label_depth > 0))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "label":
            self.label_depth = max(0, self.label_depth - 1)


def audit_product_source(architecture: ArchitectureSpec, files: list[ScaffoldFile]) -> list[QAIssue]:
    if architecture.product_design is None:
        return []  # Older/non-browser records have no v2 design contract.
    issues: list[QAIssue] = []
    by_language = {scaffold_target(c)[1]: c.name for c in architecture.components}

    def issue(language: str, message: str, fix: str, severity="major"):
        issues.append(
            QAIssue(
                component=by_language.get(language, "Product Design"),
                severity=severity,
                issue="Source audit: " + message,
                fix=fix,
            )
        )

    sources = {
        language: [f for f in files if f.language == language] for language in ("html", "css", "javascript")
    }
    for language, found in sources.items():
        if not found or not any(f.content.strip() for f in found):
            issue(
                language,
                f"Missing nonempty {language} implementation.",
                "Write the complete component against the approved scope and design contract.",
                "critical",
            )
    if not sources["html"]:
        return issues
    markup = _Markup()
    for file in sources["html"]:
        markup.feed(file.content)
    tags = markup.tags
    if sum(tag == "h1" for tag, _ in tags) != 1 or not any(tag == "main" for tag, _ in tags):
        issue(
            "html",
            "Expected one h1 and a main landmark.",
            "Give the primary task one h1 inside a semantic main region.",
        )
    if not any(tag == "title" for tag, _ in tags) or not any(
        tag == "html" and attrs.get("lang") for tag, attrs in tags
    ):
        issue(
            "html",
            "Document title or language is missing.",
            "Set a product-specific title and the document language.",
        )
    if not any(tag == "meta" and attrs.get("name", "").lower() == "viewport" for tag, attrs in tags):
        issue(
            "html",
            "Viewport metadata is missing.",
            "Use width=device-width, initial-scale=1 without disabling zoom.",
        )
    ids = [attrs["id"] for _, attrs in tags if attrs.get("id")]
    if len(ids) != len(set(ids)):
        issue(
            "html",
            "Duplicate element ids make interactions ambiguous.",
            "Assign unique ids and update dependent CSS/JS.",
        )
    labels = {attrs.get("for") for tag, attrs in tags if tag == "label"}
    for tag, attrs, wrapped in markup.controls:
        if tag == "input" and attrs.get("type", "text").lower() in {"hidden", "submit", "reset", "button"}:
            continue
        labelled_by = attrs.get("aria-labelledby", "").split()
        named = attrs.get("aria-label") or (labelled_by and all(name in ids for name in labelled_by))
        if not (wrapped or named or (attrs.get("id") and attrs["id"] in labels)):
            issue(
                "html",
                f"Unlabeled {tag} control {attrs.get('id', '(no id)')}.",
                "Add a visible associated label; placeholder alone is insufficient.",
            )
    css = "\n".join(f.content for f in sources["css"])
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for pattern, message, fix in (
        (
            r":root\s*\{[^}]*--[\w-]+\s*:",
            "Design tokens are missing.",
            "Declare the product palette, typography and spacing tokens in :root.",
        ),
        (
            r"@media\b",
            "Responsive stylesheet rules are missing.",
            "Implement the design contract's narrow-screen reflow.",
        ),
        (
            r":focus(?:-visible)?\b",
            "Keyboard focus styling is missing.",
            "Provide a visible high-contrast focus-visible treatment.",
        ),
    ):
        if not re.search(pattern, css, flags=re.I | re.S):
            issue("css", message, fix)
    missing_ids = undefined_dom_ids(files)
    if missing_ids:
        issue(
            "javascript",
            "Undefined static DOM ids: " + ", ".join(missing_ids),
            "Align the DOM references with the current markup.",
            "critical",
        )
    return issues
