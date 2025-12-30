from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, conint

app = FastAPI()


class ChecklistInput(BaseModel):
    text: str = Field(..., description="Source text to convert into checklist steps")
    context: Optional[str] = Field(None, description="Optional context for the checklist")
    max_steps: conint(ge=3, le=12) = Field(8, description="Maximum number of steps")
    audience: str = Field("agent", description="Audience must be 'agent'")


class MCPRequest(BaseModel):
    tool: str
    input: ChecklistInput


class ChecklistStep(BaseModel):
    id: str
    title: str
    action: str
    verify: str
    artifacts: List[str]


class ChecklistOutput(BaseModel):
    type: str = "checklist"
    audience: str = "agent"
    context: Optional[str]
    steps: List[ChecklistStep]
    human_summary: str


@dataclass(frozen=True)
class StepTemplate:
    title: str
    action: str
    verify: str
    artifacts: List[str]


KEYWORD_TEMPLATES = [
    (
        {"endpoint", "api"},
        StepTemplate(
            title="Publish stable endpoint",
            action="Deploy and expose a stable HTTP endpoint, then record path and method.",
            verify="Call the endpoint with curl and confirm a 200 response and correct payload shape.",
            artifacts=["stable endpoint"],
        ),
    ),
    (
        {"error", "errors", "exception", "exceptions", "handle", "handling"},
        StepTemplate(
            title="Complete error handling",
            action="Add error handling for critical flows with explicit error responses.",
            verify="Trigger a failure path and confirm the response includes status and message.",
            artifacts=[],
        ),
    ),
    (
        {"document", "docs", "documentation", "spec"},
        StepTemplate(
            title="Update documentation",
            action="Write or update documentation covering purpose, steps, and constraints.",
            verify="Check the documentation includes examples and limitation notes.",
            artifacts=["documentation"],
        ),
    ),
    (
        {"description", "describe"},
        StepTemplate(
            title="Draft requirement summary",
            action="Summarize key requirements into a short description document.",
            verify="Confirm the summary covers scope, constraints, and key terms.",
            artifacts=["description document"],
        ),
    ),
    (
        {"avoid", "prohibit", "prohibited", "ban", "banned"},
        StepTemplate(
            title="Remove prohibited items",
            action="List prohibited items and remove them from the planned work.",
            verify="Review outputs to confirm prohibited items are absent.",
            artifacts=[],
        ),
    ),
    (
        {"stable", "stability", "reliable", "reliability"},
        StepTemplate(
            title="Validate stability",
            action="Set up availability checks and record key health metrics.",
            verify="Send repeated requests and confirm there are no abnormal fluctuations.",
            artifacts=[],
        ),
    ),
]

GENERIC_TEMPLATES = [
    StepTemplate(
        title="Clarify execution scope",
        action="Define the execution scope and key constraints in a checklist.",
        verify="Verify the scope list includes goals, boundaries, and key terms.",
        artifacts=[],
    ),
    StepTemplate(
        title="Break down key tasks",
        action="Split the work into executable tasks and order them.",
        verify="Confirm the task list has a clear sequence and owners.",
        artifacts=[],
    ),
    StepTemplate(
        title="Review deliverables",
        action="List expected deliverables and mark their storage locations.",
        verify="Check each deliverable item maps to an actual output.",
        artifacts=[],
    ),
    StepTemplate(
        title="Record completion status",
        action="Log completion status for each step with a result summary.",
        verify="Ensure records include time, owner, and outcome.",
        artifacts=[],
    ),
]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def split_segments(text: str) -> List[str]:
    normalized = re.sub(r"\s+", " ", text.strip())
    if not normalized:
        return []
    parts = re.split(r"[\n.;!?。；、]+", normalized)
    segments: List[str] = []
    for part in parts:
        cleaned = part.strip(" -\t")
        if not cleaned:
            continue
        segments.extend([p.strip() for p in cleaned.split(" and ") if p.strip()])
    return segments


def select_template(segment: str) -> Optional[StepTemplate]:
    lowered = segment.lower()
    for keywords, template in KEYWORD_TEMPLATES:
        if any(keyword in lowered for keyword in keywords):
            return template
    return None


def generate_steps(text: str, max_steps: int) -> List[ChecklistStep]:
    segments = split_segments(text)
    templates: List[StepTemplate] = []
    for segment in segments:
        template = select_template(segment)
        if template:
            templates.append(template)
        if len(templates) >= max_steps:
            break

    if not templates:
        templates = GENERIC_TEMPLATES[:]

    while len(templates) < 3:
        templates.append(GENERIC_TEMPLATES[len(templates) % len(GENERIC_TEMPLATES)])

    templates = templates[:max_steps]

    steps: List[ChecklistStep] = []
    for index, template in enumerate(templates, start=1):
        steps.append(
            ChecklistStep(
                id=str(index),
                title=template.title,
                action=template.action,
                verify=template.verify,
                artifacts=template.artifacts,
            )
        )
    return steps


@app.post("/mcp")
def mcp(request: MCPRequest) -> ChecklistOutput:
    if request.tool != "generate_checklist":
        raise HTTPException(status_code=400, detail="Unknown tool")
    if request.input.audience != "agent":
        raise HTTPException(status_code=400, detail="Audience must be 'agent'")
    steps = generate_steps(request.input.text, request.input.max_steps)
    summary = f"Generated a {len(steps)}-step execution checklist."
    return ChecklistOutput(
        context=request.input.context,
        steps=steps,
        human_summary=summary,
    )
