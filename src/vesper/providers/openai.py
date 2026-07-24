from vesper.providers.base import BaseProvider, LLMResponse
from openai import OpenAI

class OpenAIProvider(BaseProvider):
    def __init__(self, model_name: str):
        """Initializes the openai client"""
        super().__init__(model_name)
        self.client = OpenAI()
        
    def generate(self, messages) -> LLMResponse:
        """Generates the response from OpenAI client."""
        response = self.client.responses.create(
            model=self.model_name,
            input=messages
        )
        
        return LLMResponse(
            content=response.output_text,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens
        )