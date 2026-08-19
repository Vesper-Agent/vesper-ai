from vesper.providers.base import BaseProvider, LLMResponse
from google import genai

class GoogleProvider(BaseProvider):
    def __init__(self, model_name: str):
        """Initializes the Gemini client."""
        super().__init__(model_name)
        self.client = genai.Client()

    def generate(self, messages) -> LLMResponse:
        """Generates the response from the Gemini client."""
        contents = [
            {
                "role": "model" if message["role"] == "assistant" else message["role"],
                "parts": [{"text": message["content"]}]
            }
            for message in messages
        ]

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=contents
        )

        return LLMResponse(
            content=response.text,
            prompt_tokens=response.usage_metadata.prompt_token_count,
            completion_tokens=response.usage_metadata.candidates_token_count
        )
