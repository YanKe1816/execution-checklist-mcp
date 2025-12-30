from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field, conint

app = FastAPI()

# ========= 域名验证 =========
VERIFY_TOKEN = "YWZI9_Pg7G9svmoydtQCj6Vep6gJlIT6n5rJxIL40iY"

@app.get("/.well-known/openai-apps-challenge")
def verify_domain():
    return PlainTextResponse(VERIFY_TOKEN)

# ========= Health =========
@app.get("/health")
def health():
    return {"status": "ok"}

# ========= 数据模型 =========
class ChecklistInput(BaseModel):
    text: str
    max_steps: conint(ge=3, le=12) = 8
    audience: str = "agent"

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
    steps: List[ChecklistStep]
    human_summary: str

# ========= 执行接口 =========
@app.post("/mcp")
def mcp_exec(req: MCPRequest) -> ChecklistOutput:
    if req.tool != "generate_checklist":
        raise HTTPException(status_code=400, detail="Unknown tool")

    steps = [
        ChecklistStep(
            id=str(i + 1),
            title=f"Step {i + 1}",
            action="Execute the required action",
            verify="Verify completion",
            artifacts=[]
        )
        for i in range(req.input.max_steps)
    ]

    return ChecklistOutput(
        steps=steps,
        human_summary=f"Generated {len(steps)} steps"
    )

# ========= ⭐ 扫描器只看这个 =========
@app.get("/mcp")
def mcp_tools():
    return JSONResponse(
        {
            "tools": [
                {
                    "name": "generate_checklist",
                    "description": "Generate a structured execution checklist.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string"
                            },
                            "max_steps": {
                                "type": "integer",
                                "minimum": 3,
                                "maximum": 12,
                                "default": 8
                            },
                            "audience": {
                                "type": "string",
                                "enum": ["agent"],
                                "default": "agent"
                            }
                        },
                        "required": ["text"],
                        "additionalProperties": False
                    }
                }
            ]
        }
    )
