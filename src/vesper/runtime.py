from typing import Optional
from pydantic import BaseModel

from vesper.factory import get_provider, calculate_cost
from vesper.models import VesperManifest
from vesper.registry import validate_manifest
from vesper.tools import VesperTool, ToolRegistry, load_entrypoint_tools
from vesper.builtin_tools import BUILTIN_TOOLS
from vesper.exceptions import BudgetExceededError

class RunResult(BaseModel):
    content: str
    cost: Optional[float]
    prompt_tokens: int
    completion_tokens: int
    session_id: Optional[str] = None
    alerted: bool = False

class Agent:
    def __init__(self, manifest: VesperManifest, tools: Optional[list[VesperTool]] = None):
        self.manifest = manifest
        self.provider = get_provider(manifest.model)
        self.registry = ToolRegistry(BUILTIN_TOOLS + (tools or []))

    @classmethod
    def from_manifest(cls, file_path: str, tools: Optional[list[VesperTool]] = None) -> "Agent":
        """Loads and validates an agent manifest from a YAML file."""
        manifest = validate_manifest(file_path)

        loaded = list(tools or [])
        if manifest.entryPoint:
            loaded += load_entrypoint_tools(manifest.entryPoint)

        return cls(manifest, loaded)

    def run(self, input: str, session: Optional[str] = None) -> RunResult:
        """Runs the agent against a single input and returns the result."""
        active_tools = self.registry.filter_by_manifest(self.manifest.tools)
        schemas = [tool.schema() for tool in active_tools.values()] or None

        budget = self.manifest.budget
        max_cost = budget.maxCostPerRun if budget else None
        alert_at = budget.alertAt if budget else None

        if max_cost is not None and calculate_cost(self.manifest.model, 0, 0) is None:
            raise BudgetExceededError(f"Cannot enforce budget: model '{self.manifest.model}' has no pricing.")

        messages = [{"role": "user", "content": input}]
        prompt_tokens = 0
        completion_tokens = 0

        while True:
            response = self.provider.generate(messages, schemas)
            prompt_tokens += response.prompt_tokens
            completion_tokens += response.completion_tokens
            cost = calculate_cost(self.manifest.model, prompt_tokens, completion_tokens)

            if max_cost is not None and cost > max_cost:
                raise BudgetExceededError(f"Run exceeded its budget of ${max_cost:.4f} (spent ${cost:.4f}).")

            if not response.tool_calls:
                return RunResult(
                    content=response.content,
                    cost=cost,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    session_id=session,
                    alerted=(alert_at is not None and cost is not None and cost >= alert_at)
                )

            messages.append({"role": "assistant", "tool_calls": [call.model_dump() for call in response.tool_calls]})

            for call in response.tool_calls:
                result = active_tools[call.name].execute(**call.arguments)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.name,
                    "content": str(result)
                })
