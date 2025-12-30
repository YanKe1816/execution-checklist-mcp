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
            title="发布稳定接口",
            action="部署并暴露稳定的 HTTP 接口，并记录路径与方法。",
            verify="使用 curl 访问接口，确认返回 200 且响应结构正确。",
            artifacts=["stable endpoint"],
        ),
    ),
    (
        {"error", "errors", "exception", "exceptions", "handle", "handling"},
        StepTemplate(
            title="补全错误处理",
            action="为关键流程添加错误处理与明确的错误响应。",
            verify="触发错误场景，确认错误响应包含状态码与说明。",
            artifacts=[],
        ),
    ),
    (
        {"document", "docs", "documentation", "spec"},
        StepTemplate(
            title="完善文档说明",
            action="编写并更新使用说明，覆盖目的、步骤与限制。",
            verify="检查文档包含示例与限制条款。",
            artifacts=["documentation"],
        ),
    ),
    (
        {"description", "describe"},
        StepTemplate(
            title="整理需求说明",
            action="整理需求要点并输出简要说明文档。",
            verify="核对说明涵盖范围、约束与关键术语。",
            artifacts=["description document"],
        ),
    ),
    (
        {"avoid", "prohibit", "prohibited", "ban", "banned"},
        StepTemplate(
            title="排除禁止项",
            action="列出禁止事项并从方案中移除相关内容。",
            verify="复核产出中不包含禁止事项。",
            artifacts=[],
        ),
    ),
    (
        {"stable", "stability", "reliable", "reliability"},
        StepTemplate(
            title="确认稳定性",
            action="设置可用性检查并记录关键健康指标。",
            verify="连续请求服务多次，确认无异常波动。",
            artifacts=[],
        ),
    ),
]

GENERIC_TEMPLATES = [
    StepTemplate(
        title="梳理执行范围",
        action="明确执行范围与关键约束，整理成清单。",
        verify="检查范围清单包含目标、边界与关键术语。",
        artifacts=[],
    ),
    StepTemplate(
        title="拆分关键任务",
        action="将工作拆分为可执行任务并排序。",
        verify="任务列表具有清晰顺序与负责人。",
        artifacts=[],
    ),
    StepTemplate(
        title="核对交付物",
        action="整理预期交付物并标注存放位置。",
        verify="交付物清单可逐项对应实际产出。",
        artifacts=[],
    ),
    StepTemplate(
        title="记录完成情况",
        action="记录每步完成情况与结果摘要。",
        verify="检查记录包含时间、责任人与结果。",
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
    summary = f"根据提供的要求生成了{len(steps)}步执行清单。"
    return ChecklistOutput(
        context=request.input.context,
        steps=steps,
        human_summary=summary,
    )
