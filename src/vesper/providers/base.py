from pydantic import BaseModel
from abc import ABC, abstractmethod
from typing import List, Optional

class ToolCall(BaseModel):
    """A single tool invocation requested by the model."""
    id: str
    name: str
    arguments: dict

class LLMResponse(BaseModel):
    """This is the standard llm response class."""
    content: str = ""
    prompt_tokens: int
    completion_tokens: int
    tool_calls: List[ToolCall] = []

class BaseProvider(ABC):
    """This is the blueprint for LLM provider class."""
    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    def generate(self, messages: List[dict], tools: Optional[List[dict]] = None) -> LLMResponse:
        """This method generates the response from the LLM."""
        pass
