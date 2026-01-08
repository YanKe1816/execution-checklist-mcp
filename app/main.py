from __future__ import annotations

import re
from typing import List, Optional

from fastapi import FastAPI
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


class ChecklistMeta(BaseModel):
    state: str
    reason: Optional[str] = None


class ChecklistOutput(BaseModel):
    type: str = "checklist"
    audience: str = "agent"
    context: Optional[str]
    steps: List[ChecklistStep]
    human_summary: str
    meta: ChecklistMeta




@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def split_segments(text: str) -> List[str]:
    stripped = text.strip()
    if not stripped:
        return []
    bullet_normalized = re.sub(r"(?:^|\n)\s*[-*•]\s+", "\n", stripped)
    parts = re.split(r"[\n]+", bullet_normalized)
    segments: List[str] = []
    for part in parts:
        cleaned = part.strip(" -\t")
        if not cleaned:
            continue
        for sentence in re.split(r"[.;!?。；、]+", cleaned):
            sentence_cleaned = sentence.strip()
            if sentence_cleaned:
                segments.append(sentence_cleaned)
    return segments


def generate_steps(text: str, max_steps: int) -> List[ChecklistStep]:
    segments = split_segments(text)
    steps: List[ChecklistStep] = []
    if not segments:
        return steps
    limited_segments = segments[:max_steps]
    while len(limited_segments) < 3:
        limited_segments.append(segments[len(limited_segments) % len(segments)])
    for index, segment in enumerate(limited_segments[:max_steps], start=1):
        title = segment[:48] if len(segment) > 48 else segment
        steps.append(
            ChecklistStep(
                id=str(index),
                title=f"Execute: {title}",
                action=f"Do the following: {segment}.",
                verify=f"Confirm completion of: {segment}.",
                artifacts=[],
            )
        )
    return steps


def generate_checklist_json(request: MCPRequest) -> ChecklistOutput:
    if request.tool != "generate_checklist":
        return ChecklistOutput(
            context=request.input.context,
            steps=[],
            human_summary="Invalid tool name.",
            meta=ChecklistMeta(state="failure", reason="tool must be generate_checklist"),
        )
    if request.input.audience != "agent":
        return ChecklistOutput(
            context=request.input.context,
            steps=[],
            human_summary="Invalid audience.",
            meta=ChecklistMeta(state="failure", reason="audience must be agent"),
        )
    if not request.input.text.strip():
        return ChecklistOutput(
            context=request.input.context,
            steps=[],
            human_summary="Invalid input text.",
            meta=ChecklistMeta(state="failure", reason="text must be non-empty"),
        )
    steps = generate_steps(request.input.text, request.input.max_steps)
    summary = f"Generated a {len(steps)}-step execution checklist."
    return ChecklistOutput(
        context=request.input.context,
        steps=steps,
        human_summary=summary,
        meta=ChecklistMeta(state="success"),
    )


@app.post("/mcp")
def mcp(request: MCPRequest) -> ChecklistOutput:
    return generate_checklist_json(request)


@app.get("/mcp")
def mcp_tools() -> dict:
    return {
        "tools": [
            {
                "name": "generate_checklist",
                "description": "Format input text into deterministic checklist steps.",
                "input_schema": {
                    "text": "string",
                    "audience": "agent",
                    "max_steps": "integer (min 3, max 12, default 8)",
                },
            }
        ]
    }
