from __future__ import annotations

import re
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


GENERIC_STEPS = [
    "澄清需求范围",
    "执行关键任务",
    "核对交付物",
    "记录完成情况",
]

ARTIFACT_KEYWORDS = {
    "endpoint": "stable endpoint",
    "api": "stable endpoint",
    "document": "documentation",
    "description": "description document",
    "spec": "spec document",
}


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


def build_title(segment: str) -> str:
    if not segment:
        return "执行任务"
    words = segment.split()
    if len(words) > 6:
        words = words[:6]
    snippet = " ".join(words)
    if len(snippet) > 24:
        snippet = snippet[:24]
    return f"执行: {snippet}"


def build_action(segment: str) -> str:
    if segment:
        return f"根据要求执行：{segment}。"
    return "根据提供的要求执行相关任务。"


def build_verify(segment: str) -> str:
    if segment:
        return f"确认已完成并符合要求：{segment}。"
    return "确认任务已完成且符合要求。"


def build_artifacts(segment: str) -> List[str]:
    artifacts: List[str] = []
    lowered = segment.lower()
    for keyword, artifact in ARTIFACT_KEYWORDS.items():
        if keyword in lowered and artifact not in artifacts:
            artifacts.append(artifact)
    return artifacts


def generate_steps(text: str, max_steps: int) -> List[ChecklistStep]:
    segments = split_segments(text)
    steps: List[ChecklistStep] = []
    for segment in segments:
        steps.append(
            ChecklistStep(
                id=str(len(steps) + 1),
                title=build_title(segment),
                action=build_action(segment),
                verify=build_verify(segment),
                artifacts=build_artifacts(segment),
            )
        )
        if len(steps) >= max_steps:
            return steps

    while len(steps) < 3:
        generic_segment = GENERIC_STEPS[len(steps) % len(GENERIC_STEPS)]
        steps.append(
            ChecklistStep(
                id=str(len(steps) + 1),
                title=build_title(generic_segment),
                action=build_action(generic_segment),
                verify=build_verify(generic_segment),
                artifacts=[],
            )
        )

    if len(steps) > max_steps:
        steps = steps[:max_steps]
        for index, step in enumerate(steps, start=1):
            step.id = str(index)
    return steps


@app.post("/mcp")
def mcp(request: MCPRequest) -> ChecklistOutput:
    if request.tool != "generate_checklist":
        raise HTTPException(status_code=400, detail="Unknown tool")
    if request.input.audience != "agent":
        raise HTTPException(status_code=400, detail="Audience must be 'agent'")
    steps = generate_steps(request.input.text, request.input.max_steps)
    summary = f"根据提供的要求生成了{len(steps)}步执行清单。"
    return ChecklistOutput(
        context=request.input.context,
        steps=steps,
        human_summary=summary,
    )
