"""Versioned, bounded problem-to-product handoff. Source text is untrusted data."""

import hashlib
import json
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, StrictBool, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Evidence(ContractModel):
    url: Annotated[HttpUrl, Field(json_schema_extra={"pattern": "^https?://"})]
    excerpt: Text
    title: Annotated[str, StringConstraints(max_length=300)] = ""


class ProblemSource(ContractModel):
    system: Literal["xploremore"] = "xploremore"
    problem_id: Annotated[int, Field(strict=True, gt=0)]
    captured_at: AwareDatetime
    statement: Text
    evidence: list[Evidence] = Field(min_length=1, max_length=10)
    voice_count: Annotated[int, Field(strict=True, ge=1)]
    source_count: Annotated[int, Field(strict=True, ge=1)]
    limitations: Text = "Machine-classified public reports; counts and grouping require human review."


class AcceptanceCriterion(ContractModel):
    given: Text
    when: Text
    then: Text


class ProductSpec(ContractModel):
    target_user: Text
    goal: Text
    delivery: Literal["browser_tool"] = "browser_tool"
    in_scope: list[Text] = Field(min_length=1, max_length=6)
    out_of_scope: list[Text] = Field(min_length=1, max_length=6)
    acceptance: list[AcceptanceCriterion] = Field(min_length=1, max_length=6)


class ProblemBrief(ContractModel):
    schema_version: Literal[1] = 1
    source: ProblemSource
    spec: ProductSpec


def canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def digest(value: dict) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def idea_snapshot(idea) -> dict:
    return {
        "schema_version": 1,
        "idea_id": idea.id,
        "title": idea.title,
        "description": idea.description,
        "source_url": idea.source_url,
        "reasoning": idea.reasoning,
        "problem_id": idea.xploremore_problem_id,
        "provenance": json.loads(idea.provenance) if idea.provenance else None,
        "brief": json.loads(idea.problem_brief) if idea.problem_brief else None,
    }


class FunctionalCheck(ContractModel):
    criterion: Annotated[int, Field(strict=True, ge=0, le=5)]
    passed: StrictBool
    observation: Text


class ArtifactDecision(ContractModel):
    artifact_sha256: Annotated[str, StringConstraints(pattern="^[a-f0-9]{64}$")]
    decision: Literal["accept", "reject"]
    checks: list[FunctionalCheck] = Field(min_length=1, max_length=6)
    method: Text


def artifact_digest(dossier: dict) -> str:
    files = dossier.get("scaffold_files", [])
    return digest(
        {
            "files": sorted(
                [{"path": f["path"], "content": f["content"]} for f in files], key=lambda f: f["path"]
            )
        }
    )
