from __future__ import annotations

from typing import List, Optional
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field, conint

# =========================
# 基础 App
# =========================
app = FastAPI(title="Execution Checklist MCP")

# =========================
# 👉 换成你 OpenAI 页面显示的 token
# =========================
VERIFY_TOKEN = "YWZI9_Pg7G9svmoydtQCj6Vep6gJlIT6n5rJxIL40iY"


# =========================
# Domain Verification
# =========================
@app.get("/.well-known/openai-apps-challenge")
def verify_domain():
    return PlainTextResponse(VERIFY_TOKEN)


# =========================
# Health Check
# =========================
@app.get("/health")
def health():
    return {"status": "ok"}


# =========================
# 数据模型
# =========================
class ChecklistInput(BaseModel):
    text: str = Field(..., description="Source text to convert into checklist steps")
    context: Optional[str] = Field(None, description="Optional context")
    max_steps: conint(ge=3, le=12) = Field(8, description="Maximum number of steps")
    audience: str = Field("agent", description="Must be agent")


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


# =========================
# 生成逻辑
# =========================
@dataclass(frozen=True)
class StepTemplate:
    title: str
    action: str
    verify: str
    artifacts: List[str]


TEMPLATES = [
    StepTemplate(
        title="Clarify execution scope",
        action="Define goals, boundaries, and constraints.",
        verify="Scope includes goals and limits.",
        artifacts=[],
    ),
    StepTemplate(
        title="Break down tasks",
        action="Split work into executable tasks.",
        verify="Tasks are atomic and ordered.",
        artifacts=[],
    ),
    StepTemplate(
        title="Assign ownership",
        action="Assign each task to an owner or system.",
        verify="Each task has a clear owner.",
        artifacts=[],
    ),
    StepTemplate(
        title="Define deliverables",
        action="Specify concrete outputs for each task.",
        verify="Each task maps to a deliverable.",
        artifacts=[],
    ),
    StepTemplate(
        title="Final review",
        action="Review checklist for completeness and risks.",
        verify="Checklist is complete and actionable.",
        artifacts=[],
    ),
]


def generate_steps(text: str, max_steps: int) -> List[ChecklistStep]:
    steps: List[ChecklistStep] = []
    for i, tpl in enumerate(TEMPLATES[:max_steps], start=1):
        steps.append(
            ChecklistStep(
                id=str(i),
                title=tpl.title,
                action=tpl.action,
                verify=tpl.verify,
                artifacts=tpl.artifacts,
            )
        )
    return steps


# =========================
# MCP 执行接口（POST）
# =========================
@app.post("/mcp")
def mcp_execute(req: MCPRequest) -> ChecklistOutput:
    if req.tool != "generate_checklist":
        raise HTTPException(status_code=400, detail="Unknown tool")

    if req.input.audience != "agent":
        raise HTTPException(status_code=400, detail="Audience must be agent")

    steps = generate_steps(req.input.text, req.input.max_steps)
    summary = f"Generated {len(steps)} execution steps."

    return ChecklistOutput(
        context=req.input.context,
        steps=steps,
        human_summary=summary,
    )


# =========================
# ⭐ MCP Tool 描述接口（GET）
# 这是 OpenAI Scan Tools 真正看的地方
# =========================
@app.get("/mcp")
def mcp_tools():
    return JSONResponse(
        {
            "tools": [
                {
                    "name": "generate_checklist",
                    "description": "Convert input text into a structured execution checklist.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "Source text"
                            },
                            "audience": {
                                "type": "string",
                                "enum": ["agent"],
                                "default": "agent"
                            },
                            "max_steps": {
                                "type": "integer",
                                "minimum": 3,
                                "maximum": 12,
                                "default": 8
                            }
                        },
                        "required": ["text"],
                        "additionalProperties": False
                    }
                }
            ]
        }
    )
