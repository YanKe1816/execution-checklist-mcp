# SPEC — Execution Checklist Generator (Agent-first)

## Goal
Convert policy / requirement / process text into a deterministic, structured execution checklist for agents.

## Non-goals (Important)
- No compliance judgments
- No pass/fail decisions
- No risk scoring
- No recommendations beyond translating text into actionable steps

## MCP Tool
Tool name: generate_checklist

### Input schema
- text: string (required)
- context: string (optional)
- max_steps: integer (optional, default 8, min 3, max 12)
- audience: must be "agent" (fixed for this version)

### Output schema (JSON)
{
  "type": "checklist",
  "audience": "agent",
  "context": "<string|null>",
  "steps": [
    {
      "id": "1",
      "title": "<short verb phrase>",
      "action": "<what to do>",
      "verify": "<how to verify completion>",
      "artifacts": ["<optional list of expected artifacts>"]
    }
  ],
  "human_summary": "<one-sentence plain Chinese summary>"
}

## Determinism / Stability
- Output must always be valid JSON with the same top-level keys.
- Steps must be ordered and numbered as strings "1"..."N".
- Keep titles short and action-oriented.
- If input is unclear, still output a checklist with generic clarification steps (do not ask questions interactively).

## Example behavior
Input: "Provide a clear description, avoid prohibited activities, expose a stable endpoint, handle errors."
Output: 4-6 steps with explicit verify fields.
