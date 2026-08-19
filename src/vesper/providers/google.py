from vesper.providers.base import BaseProvider, LLMResponse, ToolCall
from google import genai

class GoogleProvider(BaseProvider):
    def __init__(self, model_name: str):
        """Initializes the Gemini client."""
        super().__init__(model_name)
        self.client = genai.Client()

    def _to_contents(self, messages) -> list:
        """Translates the neutral message history into Gemini content parts."""
        contents = []
        for message in messages:
            if message["role"] == "tool":
                contents.append({
                    "role": "user",
                    "parts": [{"function_response": {"name": message["name"], "response": {"result": message["content"]}}}]
                })
            elif message["role"] == "assistant" and message.get("tool_calls"):
                contents.append({
                    "role": "model",
                    "parts": [{"function_call": {"name": call["name"], "args": call["arguments"]}} for call in message["tool_calls"]]
                })
            else:
                role = "model" if message["role"] == "assistant" else message["role"]
                contents.append({"role": role, "parts": [{"text": message.get("content", "")}]})
        return contents

    def generate(self, messages, tools=None) -> LLMResponse:
        """Generates the response from the Gemini client."""
        config = None
        if tools:
            config = {"tools": [{"function_declarations": tools}]}

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=self._to_contents(messages),
            config=config
        )

        tool_calls = [
            ToolCall(id=call.name, name=call.name, arguments=dict(call.args))
            for call in (response.function_calls or [])
        ]

        return LLMResponse(
            content=response.text or "",
            prompt_tokens=response.usage_metadata.prompt_token_count,
            completion_tokens=response.usage_metadata.candidates_token_count,
            tool_calls=tool_calls
        )
