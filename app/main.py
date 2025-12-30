from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, conint

app = FastAPI()


# =========================
# Domain verification (OpenAI)
# =========================
# Paste the token provided on the OpenAI "Domain verification" section.
VERIFY_TOKEN = "YWZI9_Pg7G9svmoydtQCj6Vep6gJllT6n5rlxLL4OiY"


@app.get("/.well-known/openai-api")
def openai_domain_verify():
    # Must return plain text (no JSON, no quotes)
    return PlainTextResponse(VERIFY_TOKEN)


# =========================
# Models
# =========================
class ChecklistInput(BaseModel):
    text: str = Field(..., description="Source text to convert into checklist steps")
    context: Optional[str] = Field(None, description="Optional context for the checklist")
    max_steps: conint(ge=3, le=12) = Field(5, description="Maximum number of steps")
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


# =========================
# Tool templates
# =========================
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
            title="Publish a stable endpoint",
            action="Deploy and expose a stable HTTP endpoint, then record its URL and method.",
            verify="Call the endpoint and confirm a 200 response and correct payload shape.",
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
        {"privacy", "policy"},
        StepTemplate(
            title="Prepare Privacy Policy",
            action="Create a Privacy Policy and publish it at a public URL.",
            verify="Open the URL and confirm it is accessible without login.",
            artifacts=["privacy policy URL"],
        ),
    ),
    (
        {"terms", "tos"},
        StepTemplate(
            title="Prepare Terms of Service",
            action="Create Terms of Service and publish it at a public URL.",
            verify="Open the URL and confirm it is accessible without login.",
            artifacts=["terms of service URL"],
        ),
    ),
]


def generate_steps(text: str, max_steps: int) -> List[ChecklistStep]:
    t = (text or "").strip()
    if not t:
        return [
            ChecklistStep(
                id="1",
                title="Provide input text",
                action="Add a non-empty 'text' field describing what checklist to generate.",
                verify="Confirm 'text' is not empty.",
                artifacts=[],
            )
        ]

    steps: List[ChecklistStep] = []
    lower = t.lower()

    # Keyword-driven steps (best-effort)
    used = set()
    for keywords, template in KEYWORD_TEMPLATES:
        if any(k in lower for k in keywords):
            used.add(template.title)
            steps.append(
                ChecklistStep(
                    id=str(len(steps) + 1),
                    title=template.title,
                    action=template.action,
                    verify=template.verify,
                    artifacts=template.artifacts,
                )
            )
        if len(steps) >= max_steps:
            return steps[:max_steps]

    # Generic execution checklist fallbacks
    fallback_templates = [
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
            title="Run a quick validation",
            action="Execute a small test run to validate the workflow end-to-end.",
            verify="Confirm outputs are produced and errors are handled clearly.",
            artifacts=["test output"],
        ),
        StepTemplate(
            title="Prepare submission artifacts",
            action="Prepare the demo recording, app description, and required URLs.",
            verify="Open each URL and verify it loads correctly without login.",
            artifacts=["demo video URL"],
        ),
    ]

    for template in fallback_templates:
        if len(steps) >= max_steps:
            break
        if template.title in used:
            continue
        steps.append(
            ChecklistStep(
                id=str(len(steps) + 1),
                title=template.title,
                action=template.action,
                verify=template.verify,
                artifacts=template.artifacts,
            )
        )

    return steps[:max_steps]


# =========================
# MCP: GET /mcp (for OpenAI tool scanning)
# =========================
@app.get("/mcp")
def mcp_tools() -> dict:
    # IMPORTANT:
    # OpenAI scanning expects tool metadata + a proper JSON Schema for input_schema.
    return {
        "tools": [
            {
                "name": "generate_checklist",
                "description": "Convert input text into a structured execution checklist.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Source text to convert into checklist steps",
                        },
                        "context": {
                            "type": "string",
                            "description": "Optional context",
                        },
                        "audience": {
                            "type": "string",
                            "enum": ["agent"],
                            "default": "agent",
                        },
                        "max_steps": {
                            "type": "integer",
                            "minimum": 3,
                            "maximum": 12,
                            "default": 5,
                        },
                    },
                    "required": ["text"],
                    "additionalProperties": False,
                },
            }
        ]
    }


# =========================
# MCP: POST /mcp (actual tool execution)
# =========================
@app.post("/mcp")
def mcp(request: MCPRequest) -> ChecklistOutput:
    if request.tool != "generate_checklist":
        raise HTTPException(status_code=400, detail="Unknown tool")

    if request.input.audience != "agent":
        raise HTTPException(status_code=400, detail="Audience must be 'agent'")

    steps = generate_steps(request.input.text, request.input.max_steps)
    summary = f"Generated {len(steps)} checklist steps."

    return ChecklistOutput(
        context=request.input.context,
        steps=steps,
        human_summary=summary,
    )


# =========================
# Health
# =========================
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
