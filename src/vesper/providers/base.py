from pydantic import BaseModel
from abc import ABC, abstractmethod
from typing import List

class LLMResponse(BaseModel):
    """This is the standard llm response class."""
    content: str
    prompt_tokens: int
    completion_tokens: int
    
class BaseProvider(ABC):
    """This is the blueprint for LLM provider class."""
    def __init__(self, model_name: str):
        self.model_name = model_name
    
    @abstractmethod
    def generate(self, messages: List[dict]) -> LLMResponse :
        """This method generates the response from the LLM."""
        pass