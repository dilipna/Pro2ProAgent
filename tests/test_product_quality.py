"""Design contract and completion gates; no model or network calls."""

from pathlib import Path

import pytest

from p2pops.build import agents, graph
from p2pops.build.quality import audit_product_source
from p2pops.build.schemas import (
    ArchitectureSpec,
    BuildPlan,
    ComponentSpec,
    ProductDesign,
    QAIssue,
    QAReport,
    ScaffoldFile,
)
from p2pops.build.scoring import ensure_browser_components, qa_gate
from p2pops.venture import agents as venture_agents


def design():
    return ProductDesign(
        primary_workflow="Inspect an agent action, record a reason, then export the local decision.",
        layout="An action queue beside a scoped proposal inspector, with a decision trail below.",
        visual_direction="Warm ivory #f5f4ef, forest #233e30, restrained rust #b84726; serif task heading and sans controls.",
        signature_detail="Keep the exact proposed tool input beside the decision note.",
        states=[
            "Clearly labeled illustrative examples",
            "Deliberately empty workspace",
            "Invalid note",
            "Recorded decision",
        ],
        responsive_rules="Stack queue and inspector at 390px; two columns at 1440px. Visible keyboard focus and 44px actions.",
    )


def architecture():
    return ArchitectureSpec(
        components=[
            ComponentSpec(name=name, responsibility="One browser file", tech=tech)
            for name, tech in [
                ("Page", "HTML page"),
                ("Style", "CSS stylesheet"),
                ("Logic", "JavaScript browser logic"),
            ]
        ],
        data_model="review {id, decision, note}",
        rationale="Local action inspection",
        product_design=design(),
    )


def reference_files():
    root = Path(__file__).resolve().parents[1] / "examples/decision-desk"
    return [
        ScaffoldFile(component=name, path=path, language=lang, content=(root / path).read_text())
        for name, path, lang in [
            ("Page", "index.html", "html"),
            ("Style", "styles.css", "css"),
            ("Logic", "app.js", "javascript"),
        ]
    ]


@pytest.mark.parametrize(
    "verdict,severity,passed",
    [
        ("approved", "major", False),
        ("approved", "critical", False),
        ("needs_revision", "minor", False),
        ("blocked", "minor", False),
        ("approved", "minor", True),
    ],
)
def test_design_findings_cannot_be_overridden_by_optimistic_verdict(verdict, severity, passed):
    report = QAReport(
        verdict=verdict,
        reasoning="Review finding",
        issues=[
            QAIssue(
                component="Style",
                severity=severity,
                issue="Task layout is missing",
                fix="Implement the inspector",
            )
        ],
    )
    assert qa_gate(report, 1).passed is passed


def test_reference_meets_source_floor_but_is_not_claimed_browser_verified():
    assert audit_product_source(architecture(), reference_files()) == []


def test_missing_styles_unlabeled_input_and_duplicate_ids_are_actionable():
    files = reference_files()
    files[
        0
    ].content = '<html><head><title>Test</title></head><body><input id="x"><input id="x"></body></html>'
    files[1].content = "/* :root {--fake: red} @media :focus-visible */ body {color:black}"
    findings = audit_product_source(architecture(), files)
    messages = " ".join(i.issue for i in findings)
    for phrase in [
        "main landmark",
        "language",
        "Viewport",
        "Duplicate",
        "Unlabeled",
        "tokens",
        "Responsive",
        "focus",
    ]:
        assert phrase in messages
    assert {i.component for i in findings} == {"Page", "Style"}
    assert not qa_gate(QAReport(verdict="approved", reasoning="optimistic", issues=findings), 1).passed


def test_missing_files_and_dom_references_are_critical():
    files = reference_files()
    files[2].content += "\ndocument.getElementById('not-real');"
    findings = audit_product_source(architecture(), [files[0], files[2]])
    assert any(i.component == "Style" and i.severity == "critical" for i in findings)
    assert any("not-real" in i.issue and i.severity == "critical" for i in findings)


def test_legacy_dossier_remains_readable_without_inventing_design_evidence():
    legacy = architecture().model_dump(exclude={"product_design"})
    parsed = ArchitectureSpec.model_validate(legacy)
    assert parsed.product_design is None
    assert audit_product_source(parsed, []) == []


async def test_new_browser_architect_cannot_silently_omit_design_contract(monkeypatch):
    async def fake(*args, **kwargs):
        return ArchitectureSpec.model_validate(architecture().model_dump(exclude={"product_design"}))

    monkeypatch.setattr(venture_agents, "_structured", fake)
    with pytest.raises(ValueError, match="product_design"):
        await agents.design_architecture("Approved scope", BuildPlan(features=[], tech_stack=[]))


async def test_model_approval_cannot_suppress_independent_source_findings(monkeypatch):
    async def optimistic(*args, **kwargs):
        return QAReport(verdict="approved", reasoning="Model likes it")

    async def event(*args, **kwargs):
        pass

    monkeypatch.setattr(agents, "review_scaffold", optimistic)
    monkeypatch.setattr(graph, "_event", event)
    state = {
        "ctx": "Scope",
        "plan": BuildPlan(features=[], tech_stack=[]),
        "architecture": architecture(),
        "scaffold_files": [reference_files()[0]],
        "round_index": 0,
        "qa_reports": [],
        "gates": [],
    }
    result = await graph.qa_node(state)
    assert not result["gates"][-1].passed
    assert any("Missing nonempty css" in i.issue for i in result["qa_reports"][-1].issues)


def test_browser_slate_always_has_a_stylesheet():
    result = ensure_browser_components([ComponentSpec(name="Page", responsibility="UI", tech="HTML page")])
    assert {c.tech for c in result} >= {
        "HTML page",
        "CSS stylesheet",
        "JavaScript browser logic with localStorage",
    }


async def test_major_markup_repair_also_revises_dependent_styles_and_logic(monkeypatch):
    arch = architecture()
    captured = {}

    async def run(state, components, feedback, existing_files):
        captured["names"] = [c.name for c in components]
        captured["feedback"] = feedback
        return []

    monkeypatch.setattr(graph, "_run_engineer", run)
    state = {
        "architecture": arch,
        "targets": {
            "Page": ("index.html", "html"),
            "Style": ("styles.css", "css"),
            "Logic": ("app.js", "javascript"),
        },
        "scaffold_files": reference_files(),
        "qa_reports": [
            QAReport(
                verdict="approved",
                reasoning="Repair the layout",
                issues=[
                    QAIssue(
                        component="Page",
                        severity="major",
                        issue="Inspector region missing",
                        fix="Add inspector markup",
                    )
                ],
            )
        ],
    }
    await graph.revise_node(state)
    assert captured["names"] == ["Page", "Style", "Logic"]
    assert "Inspector region missing" in captured["feedback"]["Page"]
    assert "revised markup" in captured["feedback"]["Style"]
