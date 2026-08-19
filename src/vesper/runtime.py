import uuid
import time
from typing import Optional
from pydantic import BaseModel

from vesper.factory import get_provider, calculate_cost
from vesper.models import VesperManifest
from vesper.registry import validate_manifest, get_registry
from vesper.tools import VesperTool, ToolRegistry, load_entrypoint_tools
from vesper.builtin_tools import BUILTIN_TOOLS
from vesper.memory import MemoryStore
from vesper.audit import AuditStore, RunRecord
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
        self.memory_store = MemoryStore() if manifest.memory else None
        self.audit = AuditStore()

    def runs(self) -> list:
        """Returns the recorded run history for this agent, newest first."""
        return self.audit.list(self.manifest.name)

    def _resolve_scope(self, session: Optional[str]):
        """Determines the memory scope key and session id for this run."""
        if self.manifest.memory.scope == "session":
            session_id = session or "sess_" + uuid.uuid4().hex
            return session_id, session_id
        return "project", None

    @staticmethod
    def _collect_tools(manifest: VesperManifest, tools: Optional[list[VesperTool]]) -> list:
        """Merges explicitly passed tools with those loaded from the manifest entryPoint."""
        loaded = list(tools or [])
        if manifest.entryPoint:
            loaded += load_entrypoint_tools(manifest.entryPoint)
        return loaded

    @classmethod
    def from_manifest(cls, file_path: str, tools: Optional[list[VesperTool]] = None) -> "Agent":
        """Loads and validates an agent manifest from a YAML file."""
        manifest = validate_manifest(file_path)
        return cls(manifest, cls._collect_tools(manifest, tools))

    @classmethod
    def load(cls, name: str, tools: Optional[list[VesperTool]] = None) -> "Agent":
        """Loads a deployed agent's active manifest from the registry."""
        manifest = get_registry().get_resource_config(name)
        return cls(manifest, cls._collect_tools(manifest, tools))

    def run(self, input: str, session: Optional[str] = None) -> RunResult:
        """Runs the agent against a single input and returns the result."""
        active_tools = self.registry.filter_by_manifest(self.manifest.tools)
        schemas = [tool.schema() for tool in active_tools.values()] or None

        budget = self.manifest.budget
        max_cost = budget.maxCostPerRun if budget else None
        alert_at = budget.alertAt if budget else None

        if max_cost is not None and calculate_cost(self.manifest.model, 0, 0) is None:
            raise BudgetExceededError(f"Cannot enforce budget: model '{self.manifest.model}' has no pricing.")

        run_id = "run_" + uuid.uuid4().hex[:12]
        scope_key, session_id = self._resolve_scope(session) if self.memory_store else (None, session)
        history = self.memory_store.load(self.manifest.name, scope_key, self.manifest.memory.retentionDays) if self.memory_store else []

        messages = history + [{"role": "user", "content": input}]
        prompt_tokens = 0
        completion_tokens = 0

        try:
            while True:
                response = self.provider.generate(messages, schemas)
                prompt_tokens += response.prompt_tokens
                completion_tokens += response.completion_tokens
                cost = calculate_cost(self.manifest.model, prompt_tokens, completion_tokens)

                if max_cost is not None and cost > max_cost:
                    raise BudgetExceededError(f"Run exceeded its budget of ${max_cost:.4f} (spent ${cost:.4f}).")

                if not response.tool_calls:
                    if self.memory_store:
                        self.memory_store.save(self.manifest.name, scope_key, [
                            {"role": "user", "content": input},
                            {"role": "assistant", "content": response.content}
                        ])

                    self.audit.record(RunRecord(
                        run_id=run_id, agent_name=self.manifest.name, session_id=session_id,
                        input=input, output=response.content, cost=cost,
                        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                        status="completed", created_at=time.time()
                    ))

                    return RunResult(
                        content=response.content,
                        cost=cost,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        session_id=session_id,
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

        except BudgetExceededError:
            self.audit.record(RunRecord(
                run_id=run_id, agent_name=self.manifest.name, session_id=session_id,
                input=input, output=None, cost=calculate_cost(self.manifest.model, prompt_tokens, completion_tokens),
                prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                status="failed", created_at=time.time()
            ))
            raise
