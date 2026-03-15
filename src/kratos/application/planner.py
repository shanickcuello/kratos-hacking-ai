"""Plan-and-Execute agent for autonomous pentesting.

Creates a multi-step attack plan, executes each step using the ReAct
loop, and replans when new information is discovered.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Template

from kratos.config import config
from kratos.domain.entities import (
    AttackPhase,
    Message,
    MessageRole,
    SessionState,
    ToolResult,
)
from kratos.domain.ports import DockerPort, LLMPort, UIPort
from kratos.tools import get_all_tools
from kratos.tools.guardrails import check_command

logger = logging.getLogger(__name__)

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"

PLAN_PROMPT = """You are Kratos, an autonomous cybersecurity AI agent.

Given a target and mission, create a structured attack plan.
Respond ONLY with valid JSON matching this schema:

{
  "steps": [
    {
      "id": 1,
      "phase": "recon|scanning|enumeration|exploitation|privesc|post_exploitation",
      "description": "What to do",
      "commands_hint": ["Suggested commands"],
      "depends_on": []
    }
  ]
}

Target: {{ target_ip }}
Mission: {{ mission }}
{% if context %}
Known information so far:
{{ context }}
{% endif %}
"""

STEP_PROMPT = """You are Kratos executing step {{ step_id }} of an attack plan.

## Current Step
Phase: {{ phase }}
Task: {{ description }}
Suggested commands: {{ commands_hint }}

## Overall Plan Context
{{ plan_summary }}

{% if findings %}
## Findings So Far
{{ findings }}
{% endif %}

Execute this step. Use the available tools. When done, summarize what you found.
"""


@dataclass
class PlanStep:
    """A single step in the attack plan."""

    id: int
    phase: str
    description: str
    commands_hint: list[str] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)
    status: str = "pending"  # pending | running | done | failed
    result: str = ""


@dataclass
class AttackPlan:
    """Multi-step attack plan."""

    steps: list[PlanStep] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Return a text summary of the plan."""
        lines = []
        for s in self.steps:
            icon = {"pending": "○", "running": "▶", "done": "✓", "failed": "✗"}
            lines.append(
                f"  {icon.get(s.status, '?')} Step {s.id} [{s.phase}]: {s.description}"
            )
        return "\n".join(lines)

    def next_step(self) -> PlanStep | None:
        """Return the next pending step whose dependencies are met."""
        done_ids = {s.id for s in self.steps if s.status == "done"}
        for s in self.steps:
            if s.status != "pending":
                continue
            if all(d in done_ids for d in s.depends_on):
                return s
        return None


async def _generate_plan(
    llm: LLMPort,
    target_ip: str,
    mission: str,
    context: str = "",
) -> AttackPlan:
    """Ask the LLM to generate an attack plan."""
    prompt = Template(PLAN_PROMPT).render(
        target_ip=target_ip, mission=mission, context=context,
    )
    messages = [Message(role=MessageRole.USER, content=prompt)]
    response = await llm.chat(messages)

    try:
        data = json.loads(response.content)
        steps = [
            PlanStep(
                id=s["id"],
                phase=s.get("phase", "recon"),
                description=s["description"],
                commands_hint=s.get("commands_hint", []),
                depends_on=s.get("depends_on", []),
            )
            for s in data.get("steps", [])
        ]
        return AttackPlan(steps=steps)
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to parse plan: %s", e)
        return AttackPlan(steps=[
            PlanStep(id=1, phase="recon", description=f"Scan {target_ip}"),
            PlanStep(
                id=2, phase="enumeration",
                description="Enumerate discovered services",
                depends_on=[1],
            ),
            PlanStep(
                id=3, phase="exploitation",
                description="Exploit found vulnerabilities",
                depends_on=[2],
            ),
        ])


async def _execute_step(
    step: PlanStep,
    plan: AttackPlan,
    llm: LLMPort,
    docker: DockerPort,
    ui: UIPort,
) -> str:
    """Execute a single plan step using a mini ReAct loop."""
    from kratos.application.react_agent import _execute_tool

    tools = get_all_tools()
    prompt = Template(STEP_PROMPT).render(
        step_id=step.id,
        phase=step.phase,
        description=step.description,
        commands_hint=", ".join(step.commands_hint),
        plan_summary=plan.summary(),
        findings="\n".join(plan.findings) if plan.findings else "",
    )

    messages = [Message(role=MessageRole.SYSTEM, content=prompt)]
    messages.append(
        Message(role=MessageRole.USER, content="Execute this step now.")
    )

    max_iterations = 10
    findings: list[str] = []

    for _ in range(max_iterations):
        response = await llm.chat(messages, tools)
        messages.append(response)

        if not response.tool_calls:
            if response.content:
                findings.append(response.content)
                await ui.display_assistant(response.content)
            break

        if response.content:
            await ui.display_assistant(response.content)

        for tc in response.tool_calls:
            await ui.display_status(
                f"[Step {step.id}] Running: {tc.name}"
            )
            result = await _execute_tool(
                tc.name, tc.arguments, docker
            )
            await ui.display_tool_output(tc.name, result.output)
            messages.append(
                Message(
                    role=MessageRole.TOOL,
                    content=result.output,
                    tool_call_id=tc.id,
                    name=tc.name,
                )
            )

    return "\n".join(findings)


async def run_plan_and_execute(
    llm: LLMPort,
    docker: DockerPort,
    ui: UIPort,
    target_ip: str,
    mission: str = "Full penetration test — find all flags",
) -> SessionState:
    """Run autonomous plan-and-execute loop."""
    state = SessionState()

    await ui.display_status("Generating attack plan...")
    plan = await _generate_plan(llm, target_ip, mission)
    await ui.display_assistant(f"**Attack Plan:**\n{plan.summary()}")

    while True:
        step = plan.next_step()
        if not step:
            await ui.display_status("All plan steps completed.")
            break

        step.status = "running"
        await ui.display_status(
            f"Executing step {step.id}: {step.description}"
        )

        try:
            result = await _execute_step(
                step, plan, llm, docker, ui
            )
            step.status = "done"
            step.result = result
            if result:
                plan.findings.append(
                    f"[Step {step.id}] {result[:500]}"
                )
        except Exception as e:
            step.status = "failed"
            step.result = str(e)
            logger.error("Step %d failed: %s", step.id, e)

        await ui.display_assistant(f"**Plan Progress:**\n{plan.summary()}")

    return state
