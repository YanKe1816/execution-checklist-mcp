from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, conint

app = FastAPI()

# =========================
# OpenAI Domain Verification
# =========================
VERIFY_TOKEN = "YWZI9_Pg7G9svmoydtQCj6Vep6gJlIT6n5rJxIL40iY"

@app.get("/.well-known/openai-apps-challenge")
def openai_domain_verify():
    return PlainTextResponse(VERIFY_TOKEN)


# =========
# MCP Models
# =========
class ChecklistInput(BaseModel):
    text: str = Field(..., description="Source text to convert into checklist steps")
    context: Optional[str] = Field(None, description="Optional context")
    max_steps: conint(ge=3, le=12) = Field(8)
    audience: str = Field("agent", description="Must be 'agent'")


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


# ==================
# Checklist generator
# ==================
def generate_steps(text: str, max_steps: int) -> List[ChecklistStep]:
    steps = []
    for i in range(1, max_steps + 1):
        steps.append(
            ChecklistStep(
                id=str(i),
                title=f"Step {i}",
                action=f"Perform action {i} based on: {text}",
                verify=f"Verify completion of step {i}",
                artifacts=[]
            )
        )
    return steps


# ============
# MCP POST API
# ============
@app.post("/mcp")
def mcp(request: MCPRequest) -> ChecklistOutput:
    if request.tool != "generate_checklist":
        raise HTTPException(status_code=400, detail="Unknown tool")

    if request.input.audience != "agent":
        raise HTTPException(status_code=400, detail="Audience must be 'agent'")

    steps = generate_steps(request.input.text, request.input.max_steps)

    return ChecklistOutput(
        context=request.input.context,
        steps=steps,
        human_summary=f"{len(steps)}-step execution checklist generated."
    )


# ==========================
# MCP Tool Scanner (GET /mcp)
# ==========================
@app.get("/mcp")
def mcp_tools():
    return {
        "tools": [
            {
                "name": "generate_checklist",
                "description": "Convert input text into a structured execution checklist.",
                "input_schema": {
                    "text": "string",
                    "audience": "agent",
                    "max_steps": "integer (3-12, default 8)"
                }
            }
        ]
    }


# ============
# Health check
# ============
@app.get("/health")
def health():
    return {"status": "ok"}
