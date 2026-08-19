from vesper.providers.base import BaseProvider, LLMResponse
from anthropic import Anthropic

class AnthropicProvider(BaseProvider):
    def __init__(self, model_name: str):
        """Initializes the Anthropic client."""
        super().__init__(model_name)
        self.client = Anthropic()

    def generate(self, messages) -> LLMResponse:
        """Generates the response from the Anthropic client."""
        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=4096,
            messages=messages
        )

        return LLMResponse(
            content=response.content[0].text,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens
        )
