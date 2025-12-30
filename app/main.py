from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

# ---------- Health ----------
@app.get("/health")
def health():
    return {"status": "ok"}

# ---------- MCP JSON-RPC ----------
@app.post("/mcp")
async def mcp(request: Request):
    body = await request.json()
    method = body.get("method")

    # 1️⃣ 初始化
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "result": {
                "serverInfo": {
                    "name": "execution-checklist-mcp",
                    "version": "1.0.0"
                }
            }
        }

    # 2️⃣ 扫描器最关键的一步：列出工具
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "result": {
                "tools": [
                    {
                        "name": "generate_checklist",
                        "description": "Generate a structured execution checklist.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "max_steps": {
                                    "type": "integer",
                                    "minimum": 3,
                                    "maximum": 12,
                                    "default": 8
                                }
                            },
                            "required": ["text"]
                        }
                    }
                ]
            }
        }

    # 3️⃣ 真正调用工具
    if method == "tools/call":
        params = body.get("params", {})
        args = params.get("arguments", {})
        text = args.get("text", "")

        steps = [
            f"Step {i+1}: Execute related task"
            for i in range(5)
        ]

        return {
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": "\n".join(steps)
                    }
                ]
            }
        }

    return JSONResponse(
        status_code=400,
        content={"error": "Unknown method"}
    )
