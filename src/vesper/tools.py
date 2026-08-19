import inspect
import importlib.util
from typing import Callable, Any
from vesper.exceptions import ToolNotFoundError

TYPE_MAP = {str: "string", int: "integer", float: "number", bool: "boolean"}

class VesperTool:
    """This class holds the user's function and its metadata."""
    def __init__(self, fn: Callable, description: str = None):
        self.fn = fn
        self.name = fn.__name__
        self.description = description or fn.__doc__ or "No description provided."

    def execute(self, **kwargs) -> Any:
        """This runs the actual Python function the user wrote."""
        return self.fn(**kwargs)

    def schema(self) -> dict:
        """Builds a JSON schema of the tool's parameters from its signature."""
        properties = {}
        required = []

        for name, param in inspect.signature(self.fn).parameters.items():
            properties[name] = {"type": TYPE_MAP.get(param.annotation, "string")}
            if param.default is inspect.Parameter.empty:
                required.append(name)

        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }

def tool(description: str = None):
    """It intercepts the user's function and wraps it to VesperTool class."""
    def decorator(fn: Callable) -> VesperTool:
        return VesperTool(fn=fn, description=description)
    
    return decorator

class ToolRegistry:
    """Manages a collection of registered VesperTools."""
    def __init__(self, tools: list[VesperTool] = None):
        self._tools: dict[str, VesperTool] = {}
        if tools:
            for t in tools:
                self.register(t)

    def register(self, tool: VesperTool) -> None:
        self._tools[tool.name] = tool

    def filter_by_manifest(self, allowed_names: list[str]) -> dict[str, VesperTool]:
        """Filters registered tools against the whitelist defined in the YAML manifest."""
        active_tools = {}
        for name in allowed_names:
            if name not in self._tools:
                raise ToolNotFoundError(f"Tool '{name}' specified in manifest is not registered.")
            active_tools[name] = self._tools[name]
        return active_tools

def load_entrypoint_tools(file_path: str) -> list[VesperTool]:
    """Imports a Python file and collects its registered VesperTools."""
    spec = importlib.util.spec_from_file_location("vesper_entrypoint", file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return [obj for obj in vars(module).values() if isinstance(obj, VesperTool)]